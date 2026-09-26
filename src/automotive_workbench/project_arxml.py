"""Snapshot-only ARXML static gate for version 0.4 projects."""

from __future__ import annotations

import json
from typing import Any

from automotive_workbench.arxml_bridge import digest, import_bytes


def prepare_arxml_gate(snapshots: dict[str, bytes]) -> dict[str, Any]:
    data = snapshots["arxml.arxml"]
    producer = json.loads(snapshots["provenance.json"].decode("utf-8-sig"))
    if not isinstance(producer, dict) or producer.get("arxml_sha256") != digest(data):
        raise ValueError("Producer provenance ARXML hash mismatch")
    imported = import_bytes(data, "arxml.arxml", producer)
    findings = [{**finding, "severity": "ERROR"} for finding in imported["findings"]]
    if imported["coverage"] != "supported-subset":
        findings.append(
            {
                "severity": "ERROR",
                "code": "ARXML-PROJECT-UNSUPPORTED",
                "message": "Unsupported ARXML semantics prevent project communication acceptance",
                "locator": "/unsupported",
            }
        )
    return {
        "artifact_type": "arxml-project-gate",
        "schema_version": "arxml-project-gate-0.1",
        "status": "failed" if findings else "passed",
        "coverage": imported["coverage"],
        "findings": findings,
        "import": imported,
    }


def semantic_digest(gate: dict[str, Any]) -> str:
    """Exclude formatting, UUID and XML positions; include unsupported coverage."""
    imported = gate["import"]
    semantic = {
        "objects": [
            {key: obj[key] for key in ("id", "kind", "facts")}
            for obj in imported["objects"]
        ],
        "status": gate["status"],
        "unsupported": imported["unsupported"],
    }
    return digest(json.dumps(semantic, sort_keys=True, ensure_ascii=False).encode())
