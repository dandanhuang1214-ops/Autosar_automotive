from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.evidence_bundle import (
    load_evidence_bundle_manifest,
    verify_evidence_bundle,
)


DELIVERY_KEYS = {
    "artifact_type", "schema_version", "created_at", "status", "reason",
    "chain_status", "integrity_status", "bundle_path", "manifest_path",
    "verification_path", "manifest_sha256", "verification_sha256",
    "artifact_count", "verified_artifact_count", "dependency_count",
    "verified_dependency_count",
}
RESERVED_ROOTS = {
    "bundle",
    "verification",
    "offline-verification",
    "manifest.json",
    "communication-evidence-delivery.json",
    "evidence-capsule-report.json",
    "evidence-capsule-report.md",
}


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


def _require_regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")


def _load_delivery(path: Path) -> dict[str, Any]:
    _require_regular(path, "Communication delivery receipt")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != DELIVERY_KEYS:
        raise ValueError("Communication delivery receipt must use the closed 0.1 schema")
    if payload["artifact_type"] != "communication-evidence-delivery":
        raise ValueError("Unsupported communication delivery artifact_type")
    if payload["schema_version"] != "communication-evidence-delivery-0.1":
        raise ValueError("Unsupported communication delivery schema_version")
    if payload["status"] not in {"passed", "failed", "blocked"}:
        raise ValueError("Communication delivery status is invalid")
    if payload["chain_status"] not in {"passed", "failed", "blocked"}:
        raise ValueError("Communication delivery chain status is invalid")
    if payload["status"] != payload["chain_status"]:
        raise ValueError("Communication delivery status does not match chain status")
    if payload["integrity_status"] != "passed":
        raise ValueError("Communication delivery integrity must have passed before export")
    for field in (
        "artifact_count",
        "verified_artifact_count",
        "dependency_count",
        "verified_dependency_count",
    ):
        if (
            not isinstance(payload[field], int)
            or isinstance(payload[field], bool)
            or payload[field] < 0
        ):
            raise ValueError(f"Communication delivery count is invalid: {field}")
    if payload["artifact_count"] < 1:
        raise ValueError("Communication delivery artifact_count must be positive")
    expected_paths = {
        "bundle_path": "bundle",
        "manifest_path": "manifest.json",
        "verification_path": "verification/evidence-bundle-verification.json",
    }
    if any(payload[field] != value for field, value in expected_paths.items()):
        raise ValueError("Communication delivery paths are not the supported portable layout")
    return payload


def _render_markdown(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Self-contained Evidence Capsule",
            "",
            f"- Export status: **{result['status']}**",
            f"- Source delivery status: `{result['source_delivery_status']}`",
            f"- Bundle: `{result['bundle_id']}`",
            f"- Artifacts: {result['verified_artifact_count']}/{result['artifact_count']} verified",
            f"- Dependencies: {result['verified_dependency_count']}/{result['dependency_count']} verified",
            f"- External files copied: {result['copied_external_dependency_count']}",
            f"- Manifest SHA-256: `{result['manifest_sha256']}`",
            "",
            "## Offline verification",
            "",
            "Run `workbench verify-evidence bundle manifest.json --base . --output recheck` from the capsule root.",
            "",
            "## Boundary",
            "",
            "The capsule contains only manifest-listed bundle artifacts and external dependencies. It preserves local byte-level verification after relocation, but it is not a signature, attestation, producer identity proof, or trusted archive format.",
            "",
        ]
    )


def export_evidence_capsule(
    delivery: Path,
    output: Path,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Export a verified P7 delivery with all external dependencies copied locally."""
    if delivery.is_symlink() or not delivery.is_dir():
        raise ValueError("Communication delivery must be a regular directory")
    if output.is_symlink():
        raise ValueError("Evidence capsule output must not be a symlink")
    if output.exists() and not output.is_dir():
        raise ValueError("Evidence capsule output must be a directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Evidence capsule output must be empty or absent")
    if base is not None and base.is_symlink():
        raise ValueError("Evidence capsule source base must not be a symlink")

    delivery = delivery.resolve()
    output = output.resolve()
    base = (base or Path.cwd()).resolve()
    if not base.is_dir():
        raise ValueError(f"Evidence capsule source base is not a directory: {base}")
    if (
        _relative_to(output, delivery) is not None
        or _relative_to(delivery, output) is not None
    ):
        raise ValueError("Evidence capsule output must not overlap the source delivery")

    bundle = delivery / "bundle"
    manifest_path = delivery / "manifest.json"
    verification_path = delivery / "verification" / "evidence-bundle-verification.json"
    receipt_path = delivery / "communication-evidence-delivery.json"
    _require_regular(manifest_path, "Evidence manifest")
    _require_regular(verification_path, "Evidence verification")
    receipt = _load_delivery(receipt_path)
    manifest = load_evidence_bundle_manifest(manifest_path)

    manifest_sha256 = _sha256_file(manifest_path)
    verification_sha256 = _sha256_file(verification_path)
    if receipt["manifest_sha256"] != manifest_sha256:
        raise ValueError("Communication delivery manifest SHA-256 does not match receipt")
    if receipt["verification_sha256"] != verification_sha256:
        raise ValueError("Communication delivery verification SHA-256 does not match receipt")
    source_verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        not isinstance(source_verification, dict)
        or source_verification.get("status") != "passed"
        or source_verification.get("manifest_sha256") != manifest_sha256
    ):
        raise ValueError("Communication delivery verification is not a passed manifest-bound result")
    count_pairs = (
        (receipt["artifact_count"], manifest["artifact_count"]),
        (
            receipt["verified_artifact_count"],
            source_verification.get("verified_artifact_count"),
        ),
        (receipt["dependency_count"], source_verification.get("dependency_count")),
        (
            receipt["verified_dependency_count"],
            source_verification.get("verified_dependency_count"),
        ),
    )
    if any(actual != expected for actual, expected in count_pairs):
        raise ValueError("Communication delivery counts do not match manifest verification")
    chain_report_path = bundle / "communication-evidence-report.json"
    _require_regular(chain_report_path, "Communication chain report")
    chain_report = json.loads(chain_report_path.read_text(encoding="utf-8"))
    if (
        not isinstance(chain_report, dict)
        or chain_report.get("artifact_type") != "communication-chain-evidence"
        or chain_report.get("status") != receipt["chain_status"]
    ):
        raise ValueError("Communication delivery status does not match bundled chain evidence")

    with tempfile.TemporaryDirectory() as directory:
        preflight = verify_evidence_bundle(
            bundle, manifest_path, Path(directory), base=base
        )
    if preflight["status"] != "passed":
        raise ValueError("Communication delivery no longer passes source verification")

    external: dict[str, str] = {}
    for artifact in manifest["artifacts"]:
        for dependency in artifact["depends_on"]:
            if dependency["kind"] != "external":
                continue
            ref = dependency["ref"]
            existing = external.get(ref)
            if existing is not None and existing != dependency["sha256"]:
                raise ValueError(f"External dependency has conflicting hashes: {ref}")
            if ref.split("/", 1)[0] in RESERVED_ROOTS:
                raise ValueError(f"External dependency collides with capsule layout: {ref}")
            external[ref] = dependency["sha256"]

    output.mkdir(parents=True, exist_ok=True)
    capsule_bundle = output / "bundle"
    for artifact in manifest["artifacts"]:
        source = bundle / Path(artifact["relative_path"])
        _require_regular(source, "Manifest bundle artifact")
        destination = capsule_bundle / Path(artifact["relative_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(manifest_path, output / "manifest.json")
    (output / "verification").mkdir()
    shutil.copy2(verification_path, output / "verification" / verification_path.name)
    shutil.copy2(receipt_path, output / receipt_path.name)

    for ref, expected_sha256 in sorted(external.items()):
        source = (base / Path(ref)).resolve()
        if _relative_to(source, base) is None:
            raise ValueError(f"External dependency escapes source base: {ref}")
        _require_regular(source, "External dependency")
        if _sha256_file(source) != expected_sha256:
            raise ValueError(f"External dependency SHA-256 changed during export: {ref}")
        destination = output / Path(ref)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    offline_verification = verify_evidence_bundle(
        capsule_bundle,
        output / "manifest.json",
        output / "offline-verification",
        base=output,
    )
    if offline_verification["status"] != "passed":
        raise RuntimeError("Exported evidence capsule failed offline verification")

    offline_path = output / "offline-verification" / "evidence-bundle-verification.json"
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "evidence-capsule",
        "schema_version": "evidence-capsule-0.1",
        "created_at": timestamp.isoformat(),
        "status": "passed",
        "source_delivery_status": receipt["status"],
        "bundle_id": manifest["bundle_id"],
        "bundle_path": "bundle",
        "manifest_path": "manifest.json",
        "receipt_path": "communication-evidence-delivery.json",
        "source_verification_path": "verification/evidence-bundle-verification.json",
        "offline_verification_path": "offline-verification/evidence-bundle-verification.json",
        "manifest_sha256": manifest_sha256,
        "receipt_sha256": _sha256_file(output / receipt_path.name),
        "source_verification_sha256": verification_sha256,
        "offline_verification_sha256": _sha256_file(offline_path),
        "artifact_count": manifest["artifact_count"],
        "verified_artifact_count": offline_verification["verified_artifact_count"],
        "dependency_count": offline_verification["dependency_count"],
        "verified_dependency_count": offline_verification["verified_dependency_count"],
        "external_dependency_count": len(external),
        "copied_external_dependency_count": len(external),
        "external_dependencies": [
            {"ref": ref, "sha256": sha256}
            for ref, sha256 in sorted(external.items())
        ],
    }
    (output / "evidence-capsule-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "evidence-capsule-report.md").write_text(
        _render_markdown(result), encoding="utf-8", newline="\n"
    )
    return result
