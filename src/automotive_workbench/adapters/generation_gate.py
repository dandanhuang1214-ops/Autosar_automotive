"""Import a declared Generate-Arxml export without executing its producer."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def load_generation(
    declaration: Any, base: Path, contract_bytes: bytes
) -> tuple[dict[str, bytes], dict[str, Any]]:
    keys = {"tool", "revision", "exit_code", "source_docx", "issue_report", "sha256"}
    if not isinstance(declaration, dict) or set(declaration) != keys:
        raise ValueError(
            "Generation declaration must use the closed Generate-Arxml contract"
        )
    if (
        declaration["tool"] != "Generate-Arxml"
        or not isinstance(declaration["revision"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", declaration["revision"])
    ):
        raise ValueError(
            "Generation requires Generate-Arxml and a full commit revision"
        )
    if type(declaration["exit_code"]) is not int or declaration["exit_code"] not in (
        0,
        1,
    ):
        raise ValueError("Generation exit_code must be integer 0 or 1")
    hashes = declaration["sha256"]
    if not isinstance(hashes, dict) or set(hashes) != {
        "source_docx",
        "issue_report",
        "contract",
    }:
        raise ValueError(
            "Generation requires hashes for DOCX, issue report and contract"
        )
    contents = {"contract": contract_bytes}
    for key in ("source_docx", "issue_report"):
        value = declaration[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Generation paths must be non-empty strings")
        path = base / value
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Generation source must be a regular file: {key}")
        contents[key] = path.read_bytes()
    for key, raw in contents.items():
        expected = hashes[key]
        if (
            not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or hashlib.sha256(raw).hexdigest() != expected
        ):
            raise ValueError(f"Generation source SHA-256 mismatch: {key}")
    report = json.loads(contents["issue_report"].decode("utf-8-sig"))
    contract = json.loads(contract_bytes.decode("utf-8-sig"))
    if (
        not isinstance(report, dict)
        or not {"items", "counts", "validation_errors", "core_summary"} <= report.keys()
    ):
        raise ValueError("Generation issue report is incomplete")
    items, counts, errors = (
        report["items"],
        report["counts"],
        report["validation_errors"],
    )
    if (
        not isinstance(items, list)
        or not isinstance(counts, dict)
        or not isinstance(errors, list)
        or any(not isinstance(e, str) for e in errors)
    ):
        raise ValueError("Generation issue report has invalid items/counts/errors")
    for item in items:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(k), str)
            for k in ("kind", "severity", "code", "message", "status")
        ):
            raise ValueError("Generation finding is malformed")
        if item["kind"] not in {"open_issue", "model_validation", "core_rule"} or item[
            "severity"
        ] not in {"QUESTION", "ERROR", "WARNING", "INFO"}:
            raise ValueError("Unsupported generation finding kind/severity")
        if item["status"].lower() not in {"open", "closed", "resolved"}:
            raise ValueError("Unsupported generation finding status")
    open_issues = contract.get("open_issues")
    if not isinstance(open_issues, list) or any(
        not isinstance(i, dict) or not isinstance(i.get("status"), str)
        for i in open_issues
    ):
        raise ValueError("Generated contract requires explicit open_issues")
    checks = {
        "signals": len(contract["signals"]),
        "open_issues": len(open_issues),
        "validation_errors": len(errors),
        "core_findings": sum(i["kind"] == "core_rule" for i in items),
    }
    if any(
        type(counts.get(k)) is not int or counts[k] != value
        for k, value in checks.items()
    ):
        raise ValueError("Generation report counts disagree with imported artifacts")
    if sum(i["kind"] == "open_issue" for i in items) != len(open_issues) or sum(
        i["kind"] == "model_validation" for i in items
    ) != len(errors):
        raise ValueError("Generation report findings disagree with declared counts")
    summary = report["core_summary"]
    severity_counts = {
        s: sum(i["kind"] == "core_rule" and i["severity"] == s for i in items)
        for s in ("ERROR", "WARNING", "INFO")
    }
    if (
        not isinstance(summary, dict)
        or summary.get("by_severity") != severity_counts
        or any(type(v) is not int for v in summary["by_severity"].values())
    ):
        raise ValueError("Generation CORE summary disagrees with findings")
    blocking = sum(
        i["severity"] == "ERROR"
        or (i["kind"] == "open_issue" and i["status"].lower() == "open")
        for i in items
    )
    contract_open = sum(i["status"].lower() == "open" for i in open_issues)
    failed = (
        declaration["exit_code"] != 0
        or blocking > 0
        or bool(errors)
        or contract_open > 0
    )
    result = {
        "artifact_type": "generate-arxml-gate",
        "status": "failed" if failed else "passed",
        "tool": declaration["tool"],
        "revision": declaration["revision"],
        "producer_identity_verified": False,
        "exit_code": declaration["exit_code"],
        "blocking_finding_count": blocking,
        "warning_count": sum(i["severity"] == "WARNING" for i in items),
        "finding_count": len(items),
        "findings": items,
    }
    return {
        "source.docx": contents["source_docx"],
        "generation-issues.json": contents["issue_report"],
    }, result
