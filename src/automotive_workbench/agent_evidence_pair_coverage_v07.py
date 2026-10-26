"""Replayable literal coverage check for unassessed model prose."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automotive_workbench.agent_evidence_pair_presentation_v06 import (
    load_agent_evidence_pair_presentation_v06,
    verify_agent_evidence_pair_presentation_v06,
)
from automotive_workbench.project_explanation import canonical, digest, read

VERSION = "agent-evidence-pair-model-coverage-0.7"


def _expected_line(pair: dict[str, str]) -> str:
    return (
        f"{pair['check_id']}: status={json.dumps(pair['status'], ensure_ascii=False)}; "
        f"reason={json.dumps(pair['reason'], ensure_ascii=False)}"
    )


def _body(presentation_path: Path, presentation: dict[str, Any]) -> dict[str, Any]:
    prose = presentation["model_summary"]
    lines = prose.splitlines() if prose is not None else []
    checks = [
        {
            "check_id": pair["check_id"],
            "expected_line": _expected_line(pair),
            "occurrences": lines.count(_expected_line(pair)),
        }
        for pair in presentation["pairs"]
    ]
    if prose is None:
        status = "unavailable"
    elif checks and all(item["occurrences"] == 1 for item in checks):
        status = "complete"
    else:
        status = "incomplete"
    return {
        "artifact_type": "agent-evidence-pair-model-coverage",
        "schema_version": VERSION,
        "presentation_id": presentation["result_id"],
        "presentation_sha256": hashlib.sha256(presentation_path.read_bytes()).hexdigest(),
        "coverage_status": status,
        "checks": checks,
        "semantic_assessment": "unassessed",
        "boundary": (
            "Exact line coverage detects omitted or duplicated literal pairs only. "
            "It does not establish that model relationships or other claims are supported."
        ),
    }


def assess_agent_evidence_pair_model_v07(
    report: Path, plan: dict[str, Any], presentation_path: Path
) -> dict[str, Any]:
    presentation = load_agent_evidence_pair_presentation_v06(presentation_path)
    verify_agent_evidence_pair_presentation_v06(report, plan, presentation)
    body = _body(presentation_path, presentation)
    return {"result_id": digest(body), **body}


def verify_agent_evidence_pair_model_coverage_v07(
    report: Path, plan: dict[str, Any], presentation_path: Path, result: dict[str, Any]
) -> dict[str, Any]:
    expected = assess_agent_evidence_pair_model_v07(report, plan, presentation_path)
    if canonical(result) != canonical(expected):
        raise ValueError("Model coverage differs from verified presentation")
    return {
        "status": "passed",
        "result_id": expected["result_id"],
        "coverage_status": expected["coverage_status"],
        "covered_count": sum(item["occurrences"] == 1 for item in expected["checks"]),
        "required_count": len(expected["checks"]),
        "semantic_assessment": "unassessed",
    }


def save_agent_evidence_pair_model_coverage_v07(
    report: Path, plan: dict[str, Any], presentation_path: Path,
    result: dict[str, Any], output: Path,
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Model coverage output must be absent")
    verify_agent_evidence_pair_model_coverage_v07(
        report, plan, presentation_path, result
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_pair_model_coverage_v07(path: Path) -> dict[str, Any]:
    return read(path)
