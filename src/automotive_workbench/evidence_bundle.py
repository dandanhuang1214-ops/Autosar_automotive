from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_KEYS = {
    "artifact_type", "schema_version", "bundle_id", "created_at", "producer",
    "artifact_count", "total_bytes", "artifacts",
}
ARTIFACT_KEYS = {
    "artifact_id", "relative_path", "media_type", "artifact_type", "schema_version",
    "size_bytes", "sha256", "depends_on",
}
DEPENDENCY_KEYS = {"kind", "ref", "sha256"}

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


def _safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must be a portable relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise ValueError(f"{label} must be a portable relative path")
    return value


def load_evidence_bundle_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != MANIFEST_KEYS:
        raise ValueError("Evidence bundle manifest must use the closed 0.1 schema")
    if payload["artifact_type"] != "evidence-bundle-manifest":
        raise ValueError("Unsupported evidence bundle artifact_type")
    if payload["schema_version"] != "evidence-bundle-manifest-0.1":
        raise ValueError("Unsupported evidence bundle schema_version")
    for field in ("bundle_id", "created_at", "producer"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Evidence bundle manifest requires {field}")
    if (
        not isinstance(payload["artifact_count"], int)
        or isinstance(payload["artifact_count"], bool)
        or payload["artifact_count"] < 1
    ):
        raise ValueError("Evidence bundle artifact_count must be positive")
    if (
        not isinstance(payload["total_bytes"], int)
        or isinstance(payload["total_bytes"], bool)
        or payload["total_bytes"] < 0
    ):
        raise ValueError("Evidence bundle total_bytes must be non-negative")
    if not isinstance(payload["artifacts"], list) or not payload["artifacts"]:
        raise ValueError("Evidence bundle artifacts must be a non-empty list")

    paths: list[str] = []
    total_bytes = 0
    artifacts_by_id: dict[str, dict[str, Any]] = {}
    for index, artifact in enumerate(payload["artifacts"]):
        if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_KEYS:
            raise ValueError(f"Evidence bundle artifacts[{index}] must use the closed schema")
        artifact_id = _safe_relative_path(
            artifact["artifact_id"], f"artifacts[{index}].artifact_id"
        )
        relative = _safe_relative_path(
            artifact["relative_path"], f"artifacts[{index}].relative_path"
        )
        if artifact_id != relative:
            raise ValueError(f"Evidence bundle artifact identity/path mismatch: {artifact_id}")
        for field in ("media_type", "artifact_type"):
            if not isinstance(artifact[field], str) or not artifact[field]:
                raise ValueError(f"Evidence bundle artifact requires {field}: {artifact_id}")
        if artifact["schema_version"] is not None and not isinstance(
            artifact["schema_version"], str
        ):
            raise ValueError(f"Evidence bundle artifact schema_version is invalid: {artifact_id}")
        if (
            not isinstance(artifact["size_bytes"], int)
            or isinstance(artifact["size_bytes"], bool)
            or artifact["size_bytes"] < 0
        ):
            raise ValueError(f"Evidence bundle artifact size is invalid: {artifact_id}")
        if not isinstance(artifact["sha256"], str) or re.fullmatch(
            r"[0-9a-f]{64}", artifact["sha256"]
        ) is None:
            raise ValueError(f"Evidence bundle artifact SHA-256 is invalid: {artifact_id}")
        if not isinstance(artifact["depends_on"], list):
            raise ValueError(f"Evidence bundle artifact dependencies are invalid: {artifact_id}")
        paths.append(relative)
        total_bytes += artifact["size_bytes"]
        artifacts_by_id[artifact_id] = artifact

    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("Evidence bundle artifact paths must be sorted and unique")
    if payload["artifact_count"] != len(paths) or payload["total_bytes"] != total_bytes:
        raise ValueError("Evidence bundle aggregate counts do not match artifacts")

    for artifact in payload["artifacts"]:
        dependencies: list[tuple[str, str]] = []
        for index, dependency in enumerate(artifact["depends_on"]):
            if not isinstance(dependency, dict) or set(dependency) != DEPENDENCY_KEYS:
                raise ValueError(
                    f"Evidence dependency {artifact['artifact_id']}[{index}] must use the closed schema"
                )
            if dependency["kind"] not in {"artifact", "external"}:
                raise ValueError(f"Evidence dependency kind is invalid: {artifact['artifact_id']}")
            ref = _safe_relative_path(
                dependency["ref"], f"dependency {artifact['artifact_id']}[{index}].ref"
            )
            if not isinstance(dependency["sha256"], str) or re.fullmatch(
                r"[0-9a-f]{64}", dependency["sha256"]
            ) is None:
                raise ValueError(f"Evidence dependency SHA-256 is invalid: {ref}")
            if dependency["kind"] == "artifact":
                target = artifacts_by_id.get(ref)
                if target is None or target["sha256"] != dependency["sha256"]:
                    raise ValueError(f"Evidence artifact dependency is inconsistent: {ref}")
                if ref == artifact["artifact_id"]:
                    raise ValueError(f"Evidence artifact must not depend on itself: {ref}")
            dependencies.append((dependency["kind"], ref))
        if dependencies != sorted(dependencies) or len(dependencies) != len(set(dependencies)):
            raise ValueError(
                f"Evidence dependencies must be sorted and unique: {artifact['artifact_id']}"
            )
    return payload


def _verification_inventory(bundle: Path) -> tuple[dict[str, dict[str, Any]], set[str], list[dict[str, str]]]:
    if not bundle.is_dir():
        raise ValueError(f"Evidence bundle is not a directory: {bundle}")
    regular: dict[str, dict[str, Any]] = {}
    observed: set[str] = set()
    findings: list[dict[str, str]] = []
    for path in sorted(bundle.rglob("*"), key=lambda item: item.relative_to(bundle).as_posix()):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            observed.add(relative)
            findings.append(
                {
                    "code": "EVIDENCE-SYMLINK-DETECTED",
                    "category": "unsafe-file",
                    "path": relative,
                    "message": "Bundle contains a symbolic link",
                }
            )
        elif path.is_dir():
            continue
        else:
            observed.add(relative)
            if not path.is_file():
                findings.append(
                    {
                        "code": "EVIDENCE-SPECIAL-FILE-DETECTED",
                        "category": "unsafe-file",
                        "path": relative,
                        "message": "Bundle contains a non-regular file",
                    }
                )
            else:
                regular[relative] = {
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
    return regular, observed, findings


def _render_verification(result: dict[str, Any]) -> str:
    lines = [
        "# Evidence Bundle Verification",
        "",
        f"- Bundle: `{result['bundle_id']}`",
        f"- Status: **{result['status']}**",
        f"- Artifacts: {result['verified_artifact_count']}/{result['expected_artifact_count']} verified",
        f"- Dependencies: {result['verified_dependency_count']}/{result['dependency_count']} verified",
        "",
        "## Findings",
        "",
    ]
    if result["findings"]:
        lines.extend(
            f"- `{finding['code']}` `{finding['path']}`: {finding['message']}"
            for finding in result["findings"]
        )
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def verify_evidence_bundle(
    bundle: Path,
    manifest_path: Path,
    output: Path,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    if bundle.is_symlink():
        raise ValueError("Evidence bundle root must not be a symlink")
    if manifest_path.is_symlink():
        raise ValueError("Evidence bundle manifest must not be a symlink")
    if output.is_symlink():
        raise ValueError("Evidence verification output must not be a symlink")
    if base is not None and base.is_symlink():
        raise ValueError("Evidence bundle portable base must not be a symlink")
    bundle = bundle.resolve()
    manifest_path = manifest_path.resolve()
    output = output.resolve()
    base = (base or Path.cwd()).resolve()
    _require_outside_bundle(bundle, manifest_path)
    if _relative_to(output, bundle) is not None:
        raise ValueError("Evidence verification output must be outside the bundle")
    if not base.is_dir():
        raise ValueError(f"Evidence bundle portable base is not a directory: {base}")

    manifest = load_evidence_bundle_manifest(manifest_path)
    actual, observed, findings = _verification_inventory(bundle)
    expected = {item["relative_path"]: item for item in manifest["artifacts"]}
    artifact_valid: dict[str, bool] = {}
    for relative in sorted(expected.keys() - observed):
        findings.append(
            {"code": "EVIDENCE-FILE-MISSING", "category": "missing", "path": relative, "message": "Manifest artifact is missing"}
        )
        artifact_valid[relative] = False
    for relative in sorted(observed - expected.keys()):
        findings.append(
            {"code": "EVIDENCE-FILE-UNEXPECTED", "category": "unexpected", "path": relative, "message": "Unlisted bundle file is present"}
        )
    for relative in sorted(expected.keys() & observed):
        if relative not in actual:
            artifact_valid[relative] = False
            continue
        expected_item = expected[relative]
        actual_item = actual[relative]
        if expected_item["size_bytes"] != actual_item["size_bytes"]:
            findings.append(
                {"code": "EVIDENCE-SIZE-MISMATCH", "category": "tampered", "path": relative, "message": "Artifact size differs from manifest"}
            )
            artifact_valid[relative] = False
        elif expected_item["sha256"] != actual_item["sha256"]:
            findings.append(
                {"code": "EVIDENCE-SHA256-MISMATCH", "category": "tampered", "path": relative, "message": "Artifact SHA-256 differs from manifest"}
            )
            artifact_valid[relative] = False
        else:
            artifact_valid[relative] = True

    dependency_count = 0
    verified_dependency_count = 0
    for artifact in manifest["artifacts"]:
        for dependency in artifact["depends_on"]:
            dependency_count += 1
            ref = dependency["ref"]
            if dependency["kind"] == "artifact":
                if artifact_valid.get(ref, False):
                    verified_dependency_count += 1
                else:
                    findings.append(
                        {"code": "EVIDENCE-DEPENDENCY-FAILED", "category": "dependency", "path": ref, "message": f"Internal dependency for {artifact['artifact_id']} is not verified"}
                    )
                continue
            dependency_path = (base / ref).resolve()
            if _relative_to(dependency_path, base) is None:
                raise ValueError(f"Evidence dependency escapes portable base: {ref}")
            if not dependency_path.exists():
                findings.append(
                    {"code": "EVIDENCE-DEPENDENCY-MISSING", "category": "dependency", "path": ref, "message": f"External dependency for {artifact['artifact_id']} is missing"}
                )
            elif dependency_path.is_symlink() or not dependency_path.is_file():
                findings.append(
                    {"code": "EVIDENCE-DEPENDENCY-UNSAFE", "category": "dependency", "path": ref, "message": f"External dependency for {artifact['artifact_id']} is not a regular file"}
                )
            elif _sha256_file(dependency_path) != dependency["sha256"]:
                findings.append(
                    {"code": "EVIDENCE-DEPENDENCY-SHA256-MISMATCH", "category": "dependency", "path": ref, "message": f"External dependency for {artifact['artifact_id']} differs from manifest"}
                )
            else:
                verified_dependency_count += 1

    verified_artifact_count = sum(artifact_valid.values())
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "evidence-bundle-verification",
        "schema_version": "evidence-bundle-verification-0.1",
        "bundle_id": manifest["bundle_id"],
        "verified_at": timestamp.isoformat(),
        "manifest_sha256": _sha256_file(manifest_path),
        "status": "passed" if not findings else "failed",
        "expected_artifact_count": manifest["artifact_count"],
        "actual_artifact_count": len(observed),
        "verified_artifact_count": verified_artifact_count,
        "dependency_count": dependency_count,
        "verified_dependency_count": verified_dependency_count,
        "finding_count": len(findings),
        "findings": findings,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence-bundle-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "evidence-bundle-verification.md").write_text(
        _render_verification(result), encoding="utf-8", newline="\n"
    )
    return result
