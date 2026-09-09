from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_to(path: Path, parent: Path) -> str | None:
    try:
        return path.relative_to(parent).as_posix()
    except ValueError:
        return None


def _require_outside_bundle(bundle: Path, manifest: Path) -> None:
    if _relative_to(manifest, bundle) is not None:
        raise ValueError("Evidence bundle manifest must be outside the indexed bundle")


def _scan_files(bundle: Path) -> list[Path]:
    if not bundle.is_dir():
        raise ValueError(f"Evidence bundle is not a directory: {bundle}")
    files: list[Path] = []
    for path in sorted(bundle.rglob("*"), key=lambda item: item.relative_to(bundle).as_posix()):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            raise ValueError(f"Evidence bundle must not contain symlinks: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Evidence bundle contains a non-regular file: {relative}")
        files.append(path)
    if not files:
        raise ValueError("Evidence bundle must contain at least one regular file")
    return files


def _metadata(path: Path) -> tuple[str, str, str | None, dict[str, Any] | None]:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Evidence JSON must contain an object: {path}")
        artifact_type = payload.get("artifact_type")
        if not isinstance(artifact_type, str) or not artifact_type:
            artifact_type = "json-document"
        schema_version = payload.get("schema_version", payload.get("schema"))
        if schema_version is not None and not isinstance(schema_version, str):
            raise ValueError(f"Evidence JSON schema identifier must be a string: {path}")
        return "application/json", artifact_type, schema_version, payload
    if suffix in {".md", ".markdown"}:
        return "text/markdown", "markdown-document", None, None
    if suffix in {".log", ".txt"}:
        return "text/plain", "text-document", None, None
    return "application/octet-stream", "opaque-file", None, None


def _dependency(
    source: str,
    declared_sha256: str,
    bundle: Path,
    base: Path,
    artifacts_by_path: dict[str, dict[str, Any]],
) -> dict[str, str]:
    source_path = Path(source)
    resolved = source_path.resolve() if source_path.is_absolute() else (base / source_path).resolve()
    artifact_path = _relative_to(resolved, bundle)
    if artifact_path is not None:
        artifact = artifacts_by_path.get(artifact_path)
        if artifact is None:
            raise ValueError(f"Declared dependency is not a regular bundle artifact: {source}")
        if artifact["sha256"] != declared_sha256:
            raise ValueError(f"Declared dependency SHA-256 mismatch: {source}")
        return {"kind": "artifact", "ref": artifact_path, "sha256": declared_sha256}

    external_path = _relative_to(resolved, base)
    if external_path is None:
        raise ValueError(f"Declared dependency escapes the portable base: {source}")
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"Declared external dependency is not a regular file: {source}")
    if _sha256_file(resolved) != declared_sha256:
        raise ValueError(f"Declared dependency SHA-256 mismatch: {source}")
    return {"kind": "external", "ref": external_path, "sha256": declared_sha256}


def create_evidence_bundle_manifest(
    bundle: Path,
    manifest_path: Path,
    producer: str,
    *,
    bundle_id: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(producer, str) or not producer.strip():
        raise ValueError("Evidence bundle producer must be a non-empty string")
    if bundle.is_symlink():
        raise ValueError("Evidence bundle root must not be a symlink")
    if manifest_path.is_symlink():
        raise ValueError("Evidence bundle manifest must not be a symlink")
    if base is not None and base.is_symlink():
        raise ValueError("Evidence bundle portable base must not be a symlink")
    bundle = bundle.resolve()
    manifest_path = manifest_path.resolve()
    base = (base or Path.cwd()).resolve()
    if not base.is_dir():
        raise ValueError(f"Evidence bundle portable base is not a directory: {base}")
    _require_outside_bundle(bundle, manifest_path)

    paths = _scan_files(bundle)
    artifacts: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    for path in paths:
        relative = path.relative_to(bundle).as_posix()
        media_type, artifact_type, schema_version, payload = _metadata(path)
        artifact = {
            "artifact_id": relative,
            "relative_path": relative,
            "media_type": media_type,
            "artifact_type": artifact_type,
            "schema_version": schema_version,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "depends_on": [],
        }
        artifacts.append(artifact)
        payloads[relative] = payload

    artifacts_by_path = {artifact["relative_path"]: artifact for artifact in artifacts}
    for artifact in artifacts:
        payload = payloads[artifact["relative_path"]]
        if payload is None or "source_artifacts" not in payload:
            continue
        sources = payload["source_artifacts"]
        if not isinstance(sources, list):
            raise ValueError(
                f"source_artifacts must be a list: {artifact['relative_path']}"
            )
        dependencies: list[dict[str, str]] = []
        for index, source_artifact in enumerate(sources):
            if not isinstance(source_artifact, dict):
                raise ValueError(
                    f"source_artifacts[{index}] must be an object: {artifact['relative_path']}"
                )
            source = source_artifact.get("source")
            sha256 = source_artifact.get("sha256")
            if not isinstance(source, str) or not source:
                raise ValueError(f"Declared dependency requires source: {artifact['relative_path']}")
            if (
                not isinstance(sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            ):
                raise ValueError(f"Declared dependency requires SHA-256: {artifact['relative_path']}")
            dependencies.append(
                _dependency(source, sha256, bundle, base, artifacts_by_path)
            )
        artifact["depends_on"] = sorted(
            dependencies, key=lambda item: (item["kind"], item["ref"])
        )

    identifier = bundle_id or bundle.name
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("Evidence bundle ID must be a non-empty string")
    timestamp = datetime.now(timezone.utc)
    manifest = {
        "artifact_type": "evidence-bundle-manifest",
        "schema_version": "evidence-bundle-manifest-0.1",
        "bundle_id": identifier.strip(),
        "created_at": timestamp.isoformat(),
        "producer": producer.strip(),
        "artifact_count": len(artifacts),
        "total_bytes": sum(artifact["size_bytes"] for artifact in artifacts),
        "artifacts": artifacts,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
