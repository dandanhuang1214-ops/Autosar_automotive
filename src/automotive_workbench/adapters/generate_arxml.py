from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding


def load_issue_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Not a Generate-Arxml issue report: missing items list")
    return payload


def findings_from_issue_report(path: Path) -> list[Finding]:
    payload = load_issue_report(path)
    findings: list[Finding] = []
    for raw in payload["items"]:
        if not isinstance(raw, dict):
            continue
        findings.append(Finding(
            code=str(raw.get("code") or "UNKNOWN"),
            severity=str(raw.get("severity") or "UNKNOWN"),
            message=str(raw.get("message") or ""),
            source_artifact=str(path.resolve()),
            kind=str(raw.get("kind") or "unknown"),
            field=str(raw.get("field") or ""),
            location=str(raw.get("location") or ""),
            status=str(raw.get("status") or "open"),
        ))
    return findings


def summarize_issue_report(path: Path) -> dict[str, Any]:
    payload = load_issue_report(path)
    findings = findings_from_issue_report(path)
    return {
        "artifact_type": "generate_arxml.issue_report",
        "source": str(path.resolve()),
        "mode": payload.get("mode", "unknown"),
        "counts": payload.get("counts", {}),
        "finding_count": len(findings),
        "by_severity": _count(finding.severity for finding in findings),
        "by_kind": _count(finding.kind for finding in findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def _count(values) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result

