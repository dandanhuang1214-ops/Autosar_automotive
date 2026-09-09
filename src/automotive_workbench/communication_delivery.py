from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import BusConfig
from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    verify_evidence_bundle,
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Communication Evidence Delivery",
            "",
            f"- Status: **{result['status']}**",
            f"- Communication chain: `{result['chain_status']}`",
            f"- Bundle integrity: `{result['integrity_status']}`",
            f"- Artifacts: {result['verified_artifact_count']}/{result['artifact_count']} verified",
            f"- Dependencies: {result['verified_dependency_count']}/{result['dependency_count']} verified",
            f"- Manifest SHA-256: `{result['manifest_sha256']}`",
            "",
            "## Boundary",
            "",
            "This receipt proves that one local invocation produced a communication chain, indexed its byte-level evidence, and immediately verified the resulting bundle. A blocked delivery preserves valid integrity evidence while retaining the backend-unavailable outcome. It is not a signature, attestation, remote provenance proof, or target-ECU validation.",
            "",
        ]
    )


def run_communication_delivery(
    dbc: Path,
    intent: Path,
    output: Path,
    config: BusConfig | None = None,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Run, index, verify, and summarize one local communication evidence delivery."""
    if output.is_symlink():
        raise ValueError("Communication delivery output must not be a symlink")
    if output.exists() and not output.is_dir():
        raise ValueError("Communication delivery output must be a directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Communication delivery output must be empty or absent")

    output = output.resolve()
    base = (base or Path.cwd()).resolve()
    bundle = output / "bundle"
    manifest_path = output / "manifest.json"
    verification_output = output / "verification"

    chain = run_communication_chain(
        dbc,
        intent,
        bundle,
        config or default_communication_config(),
    )
    manifest = create_evidence_bundle_manifest(
        bundle,
        manifest_path,
        "workbench run-communication-delivery",
        bundle_id=output.name,
        base=base,
    )
    verification = verify_evidence_bundle(
        bundle,
        manifest_path,
        verification_output,
        base=base,
    )

    chain_status = chain["status"]
    integrity_status = verification["status"]
    status = "failed" if integrity_status != "passed" else chain_status
    verification_path = verification_output / "evidence-bundle-verification.json"
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "communication-evidence-delivery",
        "schema_version": "communication-evidence-delivery-0.1",
        "created_at": timestamp.isoformat(),
        "status": status,
        "reason": chain.get("reason", ""),
        "chain_status": chain_status,
        "integrity_status": integrity_status,
        "bundle_path": "bundle",
        "manifest_path": "manifest.json",
        "verification_path": "verification/evidence-bundle-verification.json",
        "manifest_sha256": _sha256_file(manifest_path),
        "verification_sha256": _sha256_file(verification_path),
        "artifact_count": manifest["artifact_count"],
        "verified_artifact_count": verification["verified_artifact_count"],
        "dependency_count": verification["dependency_count"],
        "verified_dependency_count": verification["verified_dependency_count"],
    }
    (output / "communication-evidence-delivery.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "communication-evidence-delivery.md").write_text(
        _render_markdown(result), encoding="utf-8", newline="\n"
    )
    return result
