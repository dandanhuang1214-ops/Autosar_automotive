"""Render verified pair facts separately from unassessed model prose."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from automotive_workbench.agent_evidence_pair_summary import verify_agent_evidence_pair_plan
from automotive_workbench.agent_evidence_pair_summary_v04 import (
    EVIDENCE_BOUNDARY,
    verify_agent_evidence_pair_summary_result_v04,
)
from automotive_workbench.project_explanation import canonical, digest, read

RESULT_VERSION = "agent-evidence-pair-presentation-0.5"
PRESENTATION_BOUNDARY = (
    "The user-visible summary is built only from replay-verified status/reason facts. "
    "Model prose is retained separately as unassessed source material and cannot "
    "change any displayed pair or engineering status."
)


def _pairs(source: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, str]]:
    selection = source["base_result"]["trace"]["events"][0]["result"]
    if not isinstance(selection, dict) or selection.get("status") != "complete":
        return []
    pairs = selection["pairs"]
    if [pair["check_id"] for pair in pairs] != plan["check_ids"]:
        raise ValueError("Selected pair order differs from plan")
    return [
        {
            "check_id": pair["check_id"],
            "status": pair["status_fact"]["value"],
            "reason": pair["reason_fact"]["value"],
            "status_fact_id": pair["status_fact"]["fact_id"],
            "reason_fact_id": pair["reason_fact"]["fact_id"],
            "status_pointer": pair["status_fact"]["pointer"],
            "reason_pointer": pair["reason_fact"]["pointer"],
        }
        for pair in pairs
    ]


def _summary(pairs: list[dict[str, str]]) -> str | None:
    if not pairs:
        return None
    lines = [
        f"{pair['check_id']}: status={json.dumps(pair['status'], ensure_ascii=False)}; "
        f"reason={json.dumps(pair['reason'], ensure_ascii=False)}"
        for pair in pairs
    ]
    return "\n".join([*lines, "", EVIDENCE_BOUNDARY])


def build_agent_evidence_pair_presentation_v05(
    report: Path, plan: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_evidence_pair_plan(plan)
    verify_agent_evidence_pair_summary_result_v04(report, plan, source)
    pairs = _pairs(source, plan)
    body = {
        "artifact_type": "agent-evidence-pair-presentation",
        "schema_version": RESULT_VERSION,
        "presentation_status": "presented" if pairs else "unavailable",
        "source_protocol_status": source["protocol_status"],
        "semantic_assessment": "unassessed",
        "plan_id": plan["plan_id"],
        "source_result": copy.deepcopy(source),
        "pairs": pairs,
        "summary": _summary(pairs),
        "model_summary": source["model_summary"],
        "model_summary_status": "unassessed" if source["model_summary"] is not None else "unavailable",
        "boundary": PRESENTATION_BOUNDARY,
    }
    result = {"result_id": digest(body), **body}
    verify_agent_evidence_pair_presentation_v05(report, plan, result)
    return result


def verify_agent_evidence_pair_presentation_v05(
    report: Path, plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        "result_id", "artifact_type", "schema_version", "presentation_status",
        "source_protocol_status", "semantic_assessment", "plan_id", "source_result",
        "pairs", "summary", "model_summary", "model_summary_status", "boundary",
    }
    if not isinstance(result, dict) or set(result) != fields:
        raise ValueError("Invalid Agent evidence-pair presentation fields")
    verify_agent_evidence_pair_plan(plan)
    verify_agent_evidence_pair_summary_result_v04(report, plan, result["source_result"])
    source = result["source_result"]
    pairs = _pairs(source, plan)
    expected = {
        "artifact_type": "agent-evidence-pair-presentation",
        "schema_version": RESULT_VERSION,
        "presentation_status": "presented" if pairs else "unavailable",
        "source_protocol_status": source["protocol_status"],
        "semantic_assessment": "unassessed",
        "plan_id": plan["plan_id"],
        "source_result": source,
        "pairs": pairs,
        "summary": _summary(pairs),
        "model_summary": source["model_summary"],
        "model_summary_status": "unassessed" if source["model_summary"] is not None else "unavailable",
        "boundary": PRESENTATION_BOUNDARY,
    }
    if (
        result["result_id"] != digest(expected)
        or canonical(result) != canonical({"result_id": digest(expected), **expected})
    ):
        raise ValueError("Agent evidence-pair presentation differs from verified facts")
    return {
        "status": "passed",
        "result_id": result["result_id"],
        "presentation_status": result["presentation_status"],
        "source_protocol_status": result["source_protocol_status"],
        "pair_count": len(pairs),
        "semantic_assessment": "unassessed",
    }


def save_agent_evidence_pair_presentation_v05(
    report: Path, plan: dict[str, Any], result: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-pair presentation output must be absent")
    verify_agent_evidence_pair_presentation_v05(report, plan, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_pair_presentation_v05(path: Path) -> dict[str, Any]:
    return read(path)
