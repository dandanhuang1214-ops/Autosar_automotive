"""Version 0.4: append a deterministic evidence-boundary note to pair summaries."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from automotive_workbench.agent_evidence_pair_summary import (
    run_agent_evidence_pair_summary,
    verify_agent_evidence_pair_plan,
    verify_agent_evidence_pair_summary_result,
)
from automotive_workbench.agent_runtime import AgentBudget
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import canonical, digest, read

RESULT_VERSION = "agent-evidence-pair-summary-result-0.4"
MODEL_INTERFACE = (
    "ollama-complete-pair-plain-text-summary-0.3+control-boundary-0.4"
)
EVIDENCE_BOUNDARY = (
    "证据边界（由控制面附加）：此摘要仅反映所引用项目报告中记录的证据；"
    "它本身不证明物理 ECU 行为、配置写入或实车执行，也不支持超出各检查已记录原因的根因判断。"
)


def build_agent_evidence_pair_plan(goal: str, check_ids: list[str]) -> dict[str, Any]:
    """v0.4 deliberately reuses the unchanged, versioned v0.3 plan contract."""
    from automotive_workbench.agent_evidence_pair_summary import (
        build_agent_evidence_pair_plan as build_v03_plan,
    )

    return build_v03_plan(goal, check_ids)


def run_agent_evidence_pair_summary_v04(
    report: Path,
    plan: dict[str, Any],
    client: ModelClient,
    model: str,
    budget: AgentBudget | None = None,
    *,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    kwargs = {} if clock is None else {"clock": clock}
    base = run_agent_evidence_pair_summary(report, plan, client, model, budget, **kwargs)
    model_summary = base["summary"]
    summary = (
        f"{model_summary}\n\n{EVIDENCE_BOUNDARY}"
        if base["protocol_status"] == "passed" and model_summary is not None
        else None
    )
    body = {
        "artifact_type": "agent-evidence-pair-summary-result",
        "schema_version": RESULT_VERSION,
        "model_interface": MODEL_INTERFACE,
        "protocol_status": base["protocol_status"],
        "semantic_assessment": "unassessed",
        "plan_id": plan["plan_id"],
        "base_result": base,
        "model_summary": model_summary,
        "summary": summary,
        "evidence_ids": base["evidence_ids"],
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }
    result = {"result_id": digest(body), **body}
    verify_agent_evidence_pair_summary_result_v04(report, plan, result)
    return result


def verify_agent_evidence_pair_summary_result_v04(
    report: Path, plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_evidence_pair_plan(plan)
    fields = {
        "result_id", "artifact_type", "schema_version", "model_interface",
        "protocol_status", "semantic_assessment", "plan_id", "base_result",
        "model_summary", "summary", "evidence_ids", "evidence_boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result["artifact_type"] != "agent-evidence-pair-summary-result"
        or result["schema_version"] != RESULT_VERSION
        or result["model_interface"] != MODEL_INTERFACE
        or result["protocol_status"] not in {"passed", "refused", "blocked"}
        or result["semantic_assessment"] != "unassessed"
        or result["plan_id"] != plan["plan_id"]
        or result["evidence_boundary"] != EVIDENCE_BOUNDARY
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
    ):
        raise ValueError("Invalid Agent evidence-pair summary v0.4 result")
    base = result["base_result"]
    base_verification = verify_agent_evidence_pair_summary_result(report, plan, base)
    expected_summary = (
        f"{base['summary']}\n\n{EVIDENCE_BOUNDARY}"
        if base["protocol_status"] == "passed" and base["summary"] is not None
        else None
    )
    if (
        result["protocol_status"] != base["protocol_status"]
        or result["model_summary"] != base["summary"]
        or result["summary"] != expected_summary
        or result["evidence_ids"] != base["evidence_ids"]
    ):
        raise ValueError("Agent evidence-pair v0.4 summary differs from verified base result")
    return {
        "status": "passed",
        "result_id": result["result_id"],
        "plan_id": plan["plan_id"],
        "protocol_status": result["protocol_status"],
        "semantic_assessment": result["semantic_assessment"],
        "evidence_boundary": "control_plane_appended",
        "model_calls": base_verification["model_calls"],
    }


def save_agent_evidence_pair_summary_result_v04(
    report: Path, plan: dict[str, Any], result: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-pair summary v0.4 output must be absent")
    verify_agent_evidence_pair_summary_result_v04(report, plan, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_pair_summary_result_v04(path: Path) -> dict[str, Any]:
    return read(path)
