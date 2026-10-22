"""Complete status/reason evidence pairs before one plain-text model summary."""
from __future__ import annotations

import copy
import re
import time
from pathlib import Path
from typing import Any, Callable

from automotive_workbench.agent_runtime import (
    AgentBudget,
    BOUNDARY as TRACE_BOUNDARY,
    verify_agent_trace,
)
from automotive_workbench.explanation_services import ServiceError
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import (
    build_request,
    canonical,
    digest,
    read,
)

PLAN_VERSION = "agent-evidence-pair-plan-0.3"
RESULT_VERSION = "agent-evidence-pair-summary-result-0.3"
MODEL_INTERFACE = "ollama-complete-pair-plain-text-summary-0.3"
SELECTION_VERSION = "agent-evidence-pair-selection-0.3"
TOOL_NAME = "project_select_required_check_pairs"
FIELDS = ("status", "reason")
PLAN_BOUNDARY = (
    "The operator fixes every requested project check ID before inference. Each check "
    "requires one replay-verified status/reason pair; the model cannot change the list."
)
RESULT_BOUNDARY = (
    "The control plane resolves every required status/reason pair from the complete "
    "replay-verified project fact set before contacting the model service. Missing, "
    "ambiguous, or unresolved pairs are refused with zero model calls. Protocol status, "
    "evidence completeness, and semantic assessment are separate; model prose remains "
    "unassessed and cannot change engineering status or prove an external action."
)
SELECTION_BOUNDARY = (
    "Every requested check must resolve to exactly one stage status fact and one stage "
    "reason fact from the verified report. This selection is deterministic, not top-k."
)
SYNTHESIS_PROMPT = """Summarize only the complete control-plane-selected evidence pairs.
Mention every requested check by its check_id and state that check's recorded status and
reason exactly. Return plain text only: no JSON, YAML, XML, Markdown fences, tool calls,
or citation IDs. Do not merge reasons across checks. State important evidence limits.
Do not claim that a command, vendor tool, configuration write, bus access, or hardware
action occurred unless the selected evidence explicitly records it. The control plane
attaches the complete observation citation. The prose remains semantically unassessed."""

_CHECK_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_STATUS_POINTER = re.compile(r"^/checks/([A-Za-z0-9_.-]+)/status$")


def _event(previous: str | None, sequence: int, body: dict[str, Any]) -> dict[str, Any]:
    value = {"sequence": sequence, "previous_event_id": previous, **body}
    return {"event_id": digest(value), **value}


def _plain_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("plain_text_summary_missing")
    normalized = value.strip()
    if not 0 < len(normalized) <= 1000:
        raise ValueError("plain_text_summary_length_invalid")
    if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
        raise ValueError("plain_text_summary_control_character")
    return normalized


def _response_usage(response: dict[str, Any]) -> tuple[int, int]:
    prompt = response.get("prompt_eval_count")
    output = response.get("eval_count")
    if type(prompt) is not int or type(output) is not int or prompt < 0 or output < 0:
        raise ValueError("invalid_model_usage")
    return prompt, output


def build_agent_evidence_pair_plan(goal: str, check_ids: list[str]) -> dict[str, Any]:
    if not isinstance(goal, str) or not 0 < len(goal.strip()) <= 2000:
        raise ValueError("Agent evidence-pair goal must contain 1..2000 characters")
    if (
        not isinstance(check_ids, list)
        or not 1 <= len(check_ids) <= 16
        or len(set(check_ids)) != len(check_ids)
        or any(not isinstance(item, str) or not _CHECK_ID.fullmatch(item) for item in check_ids)
    ):
        raise ValueError("Agent evidence-pair check IDs must be 1..16 unique identifiers")
    body = {
        "artifact_type": "agent-evidence-pair-plan",
        "schema_version": PLAN_VERSION,
        "goal": goal.strip(),
        "check_ids": copy.deepcopy(check_ids),
        "required_fields": list(FIELDS),
        "boundary": PLAN_BOUNDARY,
    }
    return {"plan_id": digest(body), **body}


def verify_agent_evidence_pair_plan(plan: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "plan_id",
        "artifact_type",
        "schema_version",
        "goal",
        "check_ids",
        "required_fields",
        "boundary",
    }
    if not isinstance(plan, dict) or set(plan) != fields:
        raise ValueError("Invalid Agent evidence-pair plan fields")
    if (
        plan["artifact_type"] != "agent-evidence-pair-plan"
        or plan["schema_version"] != PLAN_VERSION
        or plan["required_fields"] != list(FIELDS)
        or plan["boundary"] != PLAN_BOUNDARY
    ):
        raise ValueError("Unsupported Agent evidence-pair plan")
    expected = build_agent_evidence_pair_plan(plan["goal"], plan["check_ids"])
    if canonical(plan) != canonical(expected):
        raise ValueError("Agent evidence-pair plan differs from its deterministic body")
    return {
        "status": "passed",
        "plan_id": plan["plan_id"],
        "required_pair_count": len(plan["check_ids"]),
    }


def save_agent_evidence_pair_plan(plan: dict[str, Any], output: Path) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-pair plan output must be absent")
    verify_agent_evidence_pair_plan(plan)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(plan) + "\n", encoding="utf-8", newline="\n")
    return plan


def load_agent_evidence_pair_plan(path: Path) -> dict[str, Any]:
    plan = read(path)
    verify_agent_evidence_pair_plan(plan)
    return plan


def _fact_body(fact: dict[str, Any]) -> dict[str, Any]:
    return {name: fact[name] for name in fact if name != "fact_id"}


def _verify_fact(fact: Any, *, pointer: str, artifact_id: str, field: str) -> None:
    expected_fields = {
        "fact_id",
        "source_kind",
        "artifact_id",
        "source_sha256",
        "pointer",
        "value",
    }
    if (
        not isinstance(fact, dict)
        or set(fact) != expected_fields
        or fact["source_kind"] != "project"
        or fact["artifact_id"] != artifact_id
        or fact["pointer"] != pointer
        or not isinstance(fact["source_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", fact["source_sha256"])
        or fact["fact_id"] != digest(_fact_body(fact))
    ):
        raise ValueError("Invalid Agent evidence-pair fact")
    if field == "status" and fact["value"] not in {
        "passed",
        "failed",
        "unassessed",
        "blocked",
    }:
        raise ValueError("Invalid Agent evidence-pair status value")
    if field == "reason" and (not isinstance(fact["value"], str) or not fact["value"]):
        raise ValueError("Invalid Agent evidence-pair reason value")


def _select_required_pairs(
    report_document: dict[str, Any], request: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    requirements = report_document.get("requirements")
    facts = request.get("facts")
    if not isinstance(requirements, list) or not isinstance(facts, list):
        raise ValueError("Project report cannot supply paired acceptance evidence")
    by_id: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        if isinstance(requirement, dict) and isinstance(requirement.get("id"), str):
            by_id.setdefault(requirement["id"], []).append(requirement)

    pairs: list[dict[str, Any]] = []
    for check_id in plan["check_ids"]:
        matches = by_id.get(check_id, [])
        stage: str | None = None
        check_key: str | None = None
        issue: str | None = None
        selected: dict[str, dict[str, Any] | None] = {name: None for name in FIELDS}
        if len(matches) != 1:
            issue = "requirement_missing" if not matches else "requirement_ambiguous"
        else:
            requirement = matches[0]
            pointer = requirement.get("pointer")
            stage_value = requirement.get("stage")
            match = _STATUS_POINTER.fullmatch(pointer) if isinstance(pointer, str) else None
            if not match or not isinstance(stage_value, str) or not stage_value:
                issue = "requirement_pointer_unresolved"
            else:
                stage = stage_value
                check_key = match.group(1)
                artifact_id = f"stage-{stage}"
                for field in FIELDS:
                    fact_pointer = f"/checks/{check_key}/{field}"
                    candidates = [
                        fact
                        for fact in facts
                        if isinstance(fact, dict)
                        and fact.get("artifact_id") == artifact_id
                        and fact.get("pointer") == fact_pointer
                    ]
                    if len(candidates) == 1:
                        selected[field] = copy.deepcopy(candidates[0])
                    elif len(candidates) > 1:
                        issue = issue or f"{field}_fact_ambiguous"
                    else:
                        issue = issue or f"{field}_fact_missing"
        missing = [field for field in FIELDS if selected[field] is None]
        pairs.append(
            {
                "check_id": check_id,
                "stage": stage,
                "check_key": check_key,
                "status_fact": selected["status"],
                "reason_fact": selected["reason"],
                "missing_fields": missing,
                "issue": issue,
            }
        )
    complete_count = sum(not item["missing_fields"] and item["issue"] is None for item in pairs)
    body = {
        "schema_version": SELECTION_VERSION,
        "request_id": request["request_id"],
        "report_sha256": request["report_sha256"],
        "project_status": request["project_status"],
        "question": request["question"],
        "check_ids": copy.deepcopy(plan["check_ids"]),
        "required_fields": list(FIELDS),
        "status": "complete" if complete_count == len(pairs) else "incomplete",
        "required_pair_count": len(pairs),
        "complete_pair_count": complete_count,
        "pairs": pairs,
        "boundary": SELECTION_BOUNDARY,
    }
    selection = {"selection_id": digest(body), **body}
    _verify_selection(plan, selection)
    return selection


def _verify_selection(plan: dict[str, Any], selection: dict[str, Any]) -> None:
    fields = {
        "selection_id",
        "schema_version",
        "request_id",
        "report_sha256",
        "project_status",
        "question",
        "check_ids",
        "required_fields",
        "status",
        "required_pair_count",
        "complete_pair_count",
        "pairs",
        "boundary",
    }
    if (
        not isinstance(selection, dict)
        or set(selection) != fields
        or selection["schema_version"] != SELECTION_VERSION
        or selection["question"] != plan["goal"]
        or selection["check_ids"] != plan["check_ids"]
        or selection["required_fields"] != list(FIELDS)
        or selection["boundary"] != SELECTION_BOUNDARY
        or selection["status"] not in {"complete", "incomplete"}
        or selection["project_status"] not in {
            "passed",
            "failed",
            "unassessed",
            "blocked",
        }
        or any(
            not isinstance(selection[name], str)
            or not re.fullmatch(r"[0-9a-f]{64}", selection[name])
            for name in ("request_id", "report_sha256")
        )
        or selection["selection_id"]
        != digest({name: selection[name] for name in selection if name != "selection_id"})
    ):
        raise ValueError("Invalid Agent evidence-pair selection")
    pairs = selection["pairs"]
    if not isinstance(pairs, list) or len(pairs) != len(plan["check_ids"]):
        raise ValueError("Invalid Agent evidence-pair selection count")
    complete_count = 0
    for check_id, pair in zip(plan["check_ids"], pairs, strict=True):
        if not isinstance(pair, dict) or set(pair) != {
            "check_id",
            "stage",
            "check_key",
            "status_fact",
            "reason_fact",
            "missing_fields",
            "issue",
        }:
            raise ValueError("Invalid Agent evidence-pair entry")
        stage, check_key = pair["stage"], pair["check_key"]
        if (
            pair["check_id"] != check_id
            or (stage is not None and (not isinstance(stage, str) or not stage))
            or (check_key is not None and not isinstance(check_key, str))
            or (pair["issue"] is not None and not isinstance(pair["issue"], str))
        ):
            raise ValueError("Invalid Agent evidence-pair identity")
        expected_missing = [
            field for field in FIELDS if pair[f"{field}_fact"] is None
        ]
        if pair["missing_fields"] != expected_missing:
            raise ValueError("Agent evidence-pair missing fields differ")
        if stage is None or check_key is None:
            if (
                not expected_missing
                or pair["issue"]
                not in {"requirement_missing", "requirement_ambiguous", "requirement_pointer_unresolved"}
            ):
                raise ValueError("Unresolved Agent evidence pair lacks an issue")
        else:
            artifact_id = f"stage-{stage}"
            for field in FIELDS:
                fact = pair[f"{field}_fact"]
                if fact is not None:
                    _verify_fact(
                        fact,
                        pointer=f"/checks/{check_key}/{field}",
                        artifact_id=artifact_id,
                        field=field,
                    )
            if expected_missing and pair["issue"] not in {
                f"{field}_fact_missing" for field in expected_missing
            } | {f"{field}_fact_ambiguous" for field in expected_missing}:
                raise ValueError("Incomplete Agent evidence pair lacks a field issue")
        if not expected_missing and pair["issue"] is None:
            complete_count += 1
        elif not expected_missing:
            raise ValueError("Agent evidence pair has facts but remains unresolved")
    expected_status = "complete" if complete_count == len(pairs) else "incomplete"
    if (
        selection["required_pair_count"] != len(pairs)
        or selection["complete_pair_count"] != complete_count
        or selection["status"] != expected_status
    ):
        raise ValueError("Agent evidence-pair completeness differs")


def _select_from_report(report: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if report.is_symlink() or not report.is_file():
        raise ValueError("Agent evidence-pair report must be a regular non-symlink file")
    initial = report.read_bytes()
    document = read(report)
    request = build_request(report, plan["goal"])
    if report.read_bytes() != initial:
        raise ValueError("Project report changed during paired evidence selection")
    return _select_required_pairs(document, request, plan)


def _manifest() -> list[dict[str, Any]]:
    return [
        {
            "name": TOOL_NAME,
            "description": (
                "Replay the bound project report and select every predeclared check's "
                "complete status/reason pair without top-k retrieval."
            ),
            "permission": "read",
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["check_ids"],
                "properties": {
                    "check_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 16,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "pattern": "^[A-Za-z0-9_.-]{1,128}$",
                        },
                    }
                },
            },
            "supersedes": [],
        }
    ]


def _projection(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": selection["schema_version"],
        "selection_id": selection["selection_id"],
        "project_status": selection["project_status"],
        "status": selection["status"],
        "required_pair_count": selection["required_pair_count"],
        "complete_pair_count": selection["complete_pair_count"],
        "pairs": copy.deepcopy(selection["pairs"]),
    }


def _completeness(
    plan: dict[str, Any], selection: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    if selection is None:
        return {
            "status": "unavailable",
            "required_pair_count": len(plan["check_ids"]),
            "complete_pair_count": 0,
            "checks": [],
            "error": error or "selection_unavailable",
        }
    return {
        "status": selection["status"],
        "required_pair_count": selection["required_pair_count"],
        "complete_pair_count": selection["complete_pair_count"],
        "checks": [
            {
                "check_id": pair["check_id"],
                "stage": pair["stage"],
                "check_key": pair["check_key"],
                "missing_fields": copy.deepcopy(pair["missing_fields"]),
                "issue": pair["issue"],
            }
            for pair in selection["pairs"]
        ],
        "error": None,
    }


def _model_context(plan: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal": plan["goal"],
        "plan_id": plan["plan_id"],
        "required_check_ids": copy.deepcopy(plan["check_ids"]),
        "evidence_pairs": [
            {
                "check_id": pair["check_id"],
                "check_key": pair["check_key"],
                "status": {
                    "fact_id": pair["status_fact"]["fact_id"],
                    "pointer": pair["status_fact"]["pointer"],
                    "value": pair["status_fact"]["value"],
                },
                "reason": {
                    "fact_id": pair["reason_fact"]["fact_id"],
                    "pointer": pair["reason_fact"]["pointer"],
                    "value": pair["reason_fact"]["value"],
                },
            }
            for pair in selection["pairs"]
        ],
        "boundary": RESULT_BOUNDARY,
    }


def _request(
    plan: dict[str, Any],
    selection: dict[str, Any],
    model: str,
    budget: AgentBudget,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYNTHESIS_PROMPT},
            {"role": "user", "content": canonical(_model_context(plan, selection))},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "seed": 0,
            "num_ctx": budget.context_window,
            "num_predict": min(
                budget.max_output_tokens_per_call, budget.max_total_tokens
            ),
        },
        "keep_alive": "2m",
    }


def run_agent_evidence_pair_summary(
    report: Path,
    plan: dict[str, Any],
    client: ModelClient,
    model: str,
    budget: AgentBudget | None = None,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    verify_agent_evidence_pair_plan(plan)
    if not isinstance(model, str) or not model:
        raise ValueError("Agent evidence-pair model must be nonempty")
    actual_budget = budget or AgentBudget(
        max_steps=2,
        max_model_calls=1,
        max_tool_calls=1,
        max_output_tokens_per_call=512,
    )
    if actual_budget.max_steps < 2 or actual_budget.max_tool_calls < 1:
        raise ValueError("Agent evidence-pair summary requires one read and one model step")
    started = clock()

    def elapsed() -> float:
        return max(0.0, clock() - started)

    events: list[dict[str, Any]] = []
    exchange: dict[str, Any] = {"request": None, "response": None}
    selection: dict[str, Any] | None = None
    selection_error: str | None = None
    status = "blocked"
    reason = "selection_unavailable"
    identity: dict[str, Any] | None = None
    service_version: str | None = None
    final: dict[str, Any] | None = None
    prompt_tokens = output_tokens = model_calls = 0
    arguments = {"check_ids": copy.deepcopy(plan["check_ids"])}
    call_id = digest({"tool_name": TOOL_NAME, "arguments": arguments})
    try:
        selection = _select_from_report(report, plan)
        if (
            len(canonical(selection)) > actual_budget.max_observation_chars
            or len(canonical(_projection(selection)))
            > actual_budget.max_observation_chars
        ):
            raise ValueError("Agent evidence-pair selection exceeds observation budget")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        selection = None
        selection_error = str(exc)
    if selection is None:
        events.append(
            _event(
                None,
                1,
                {
                    "kind": "tool",
                    "tool_name": TOOL_NAME,
                    "arguments": arguments,
                    "call_id": call_id,
                    "status": "blocked",
                    "result": None,
                    "result_sha256": None,
                    "model_projection": None,
                    "projection_sha256": None,
                    "observation_id": None,
                    "error": selection_error or "selection_unavailable",
                },
            )
        )
        reason = selection_error or "selection_unavailable"
        observation_id = None
    else:
        projection = _projection(selection)
        result_sha256 = digest(selection)
        projection_sha256 = digest(projection)
        observation_id = digest(
            {
                "call_id": call_id,
                "result_sha256": result_sha256,
                "projection_sha256": projection_sha256,
            }
        )
        events.append(
            _event(
                None,
                1,
                {
                    "kind": "tool",
                    "tool_name": TOOL_NAME,
                    "arguments": arguments,
                    "call_id": call_id,
                    "status": "passed",
                    "result": selection,
                    "result_sha256": result_sha256,
                    "model_projection": projection,
                    "projection_sha256": projection_sha256,
                    "observation_id": observation_id,
                    "error": None,
                },
            )
        )
        if selection["status"] != "complete":
            status, reason = "refused", "required_evidence_pairs_incomplete"
        elif elapsed() > actual_budget.max_seconds:
            status, reason = "refused", "wall_clock_budget_exhausted"
        else:
            try:
                if not (
                    client.capabilities.identity_pinning
                    and client.capabilities.usage_metrics
                ):
                    raise ValueError("Model client lacks evidence-summary identity or usage support")
                service_version = client.service_version()
                identity = client.identity(model)
                if not isinstance(identity, dict):
                    raise ServiceError("invalid_model_identity")
                request = _request(plan, selection, model, actual_budget)
                exchange["request"] = copy.deepcopy(request)
                action: dict[str, Any] | None = None
                action_error: str | None = None
                response_sha256: str | None = None
                response_content: str | None = None
                response: Any = None
                try:
                    response = client.complete(copy.deepcopy(request))
                    model_calls = 1
                    if isinstance(response, dict):
                        exchange["response"] = copy.deepcopy(response)
                        response_sha256 = digest(response)
                        message = response.get("message")
                        if isinstance(message, dict) and isinstance(message.get("content"), str):
                            response_content = message["content"][:8000]
                        prompt_tokens, output_tokens = _response_usage(response)
                    if (
                        not isinstance(response, dict)
                        or response.get("done") is not True
                        or response.get("done_reason") != "stop"
                        or response.get("model") != model
                        or not isinstance(response.get("message"), dict)
                        or response["message"].get("role") != "assistant"
                        or response["message"].get("tool_calls")
                        or not isinstance(response["message"].get("content"), str)
                    ):
                        raise ValueError("incomplete_or_invalid_plain_text_response")
                    if prompt_tokens + output_tokens > actual_budget.context_window:
                        raise ValueError("invalid_or_exceeded_context_budget")
                    action = {
                        "action": "finish",
                        "tool_name": "",
                        "arguments": {},
                        "summary": _plain_text(response["message"]["content"]),
                        "evidence_ids": [observation_id],
                    }
                except (OSError, ValueError, TypeError, KeyError, ServiceError) as exc:
                    if model_calls == 0:
                        model_calls = 1
                    action_error = str(exc)
                events.append(
                    _event(
                        events[-1]["event_id"],
                        2,
                        {
                            "kind": "model",
                            "request_sha256": digest(request),
                            "response_sha256": response_sha256,
                            "response_content": response_content,
                            "usage": {
                                "prompt_tokens": prompt_tokens,
                                "output_tokens": output_tokens,
                            },
                            "action": action,
                            "error": action_error,
                        },
                    )
                )
                if action is None:
                    status, reason = "blocked", action_error or "invalid_plain_text_summary"
                elif client.identity(model) != identity:
                    status, reason = "refused", "model_identity_changed"
                elif elapsed() > actual_budget.max_seconds:
                    status, reason = "refused", "wall_clock_budget_exhausted"
                elif output_tokens > request["options"]["num_predict"]:
                    status, reason = "refused", "model_output_token_budget_exhausted"
                elif prompt_tokens + output_tokens > actual_budget.max_total_tokens:
                    status, reason = "refused", "token_budget_exhausted"
                else:
                    final = {
                        "summary": action["summary"],
                        "evidence_ids": action["evidence_ids"],
                        "semantic_status": "unassessed",
                    }
                    status, reason = "passed", "complete_pairs_summarized"
            except (OSError, ValueError, TypeError, KeyError, ServiceError) as exc:
                status, reason = "blocked", str(exc)

    trace_body = {
        "schema_version": "readonly-agent-trace-0.1",
        "status": status,
        "reason": reason,
        "semantic_status": "unassessed",
        "goal": plan["goal"],
        "model": identity,
        "service_version": service_version,
        "tool_manifest": _manifest(),
        "budget": actual_budget.as_dict(),
        "usage": {
            "model_calls": model_calls,
            "tool_calls": 1,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": prompt_tokens + output_tokens,
            "elapsed_ms": round(elapsed() * 1000, 3),
        },
        "events": events,
        "final": final,
        "boundary": TRACE_BOUNDARY,
    }
    trace = {"trace_id": digest(trace_body), **trace_body}
    verify_agent_trace(trace)
    body = {
        "artifact_type": "agent-evidence-pair-summary-result",
        "schema_version": RESULT_VERSION,
        "model_interface": MODEL_INTERFACE,
        "protocol_status": status,
        "evidence_completeness": _completeness(plan, selection, selection_error),
        "semantic_assessment": "unassessed",
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "summary": final["summary"] if final is not None else None,
        "evidence_ids": final["evidence_ids"] if final is not None else [],
        "model_exchange": exchange,
        "trace": trace,
        "boundary": RESULT_BOUNDARY,
    }
    result = {"result_id": digest(body), **body}
    verify_agent_evidence_pair_summary_result(report, plan, result)
    return result


def verify_agent_evidence_pair_summary_result(
    report: Path, plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_evidence_pair_plan(plan)
    fields = {
        "result_id",
        "artifact_type",
        "schema_version",
        "model_interface",
        "protocol_status",
        "evidence_completeness",
        "semantic_assessment",
        "plan_id",
        "trace_id",
        "summary",
        "evidence_ids",
        "model_exchange",
        "trace",
        "boundary",
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
        or result["boundary"] != RESULT_BOUNDARY
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
    ):
        raise ValueError("Invalid Agent evidence-pair summary result")
    trace = result["trace"]
    verification = verify_agent_trace(trace)
    if (
        result["trace_id"] != trace["trace_id"]
        or result["protocol_status"] != trace["status"]
        or trace["goal"] != plan["goal"]
        or trace["tool_manifest"] != _manifest()
    ):
        raise ValueError("Agent evidence-pair result differs from its trace")
    events = trace["events"]
    tool_events = [event for event in events if event["kind"] == "tool"]
    model_events = [event for event in events if event["kind"] == "model"]
    arguments = {"check_ids": plan["check_ids"]}
    if (
        len(tool_events) != 1
        or tool_events[0]["tool_name"] != TOOL_NAME
        or tool_events[0]["arguments"] != arguments
        or events[0] != tool_events[0]
        or len(model_events) > 1
    ):
        raise ValueError("Agent evidence-pair trace changed the fixed selection")
    event = tool_events[0]
    selection = event["result"] if event["status"] == "passed" else None
    if selection is not None:
        _verify_selection(plan, selection)
        rebuilt = _select_from_report(report, plan)
        if canonical(selection) != canonical(rebuilt):
            raise ValueError("Agent evidence-pair selection differs from replayed project report")
        if event["model_projection"] != _projection(selection):
            raise ValueError("Agent evidence-pair projection differs")
    elif report.is_symlink() or not report.is_file():
        raise ValueError("Agent evidence-pair report must be a regular non-symlink file")
    expected_completeness = _completeness(
        plan, selection, event["error"] if selection is None else None
    )
    if result["evidence_completeness"] != expected_completeness:
        raise ValueError("Agent evidence-pair completeness envelope differs")
    exchange = result["model_exchange"]
    if not isinstance(exchange, dict) or set(exchange) != {"request", "response"}:
        raise ValueError("Invalid Agent evidence-pair model exchange")
    if selection is None:
        if (
            result["protocol_status"] != "blocked"
            or model_events
            or exchange != {"request": None, "response": None}
            or trace["model"] is not None
            or trace["service_version"] is not None
        ):
            raise ValueError("Unavailable paired evidence contacted the model")
    elif selection["status"] == "incomplete":
        if (
            result["protocol_status"] != "refused"
            or trace["reason"] != "required_evidence_pairs_incomplete"
            or model_events
            or exchange != {"request": None, "response": None}
            or trace["usage"]["model_calls"] != 0
            or trace["model"] is not None
            or trace["service_version"] is not None
        ):
            raise ValueError("Incomplete paired evidence did not refuse before the model")
    elif model_events:
        if len(events) != 2 or events[1] != model_events[0] or trace["model"] is None:
            raise ValueError("Agent evidence-pair model call order differs")
        request, response = exchange["request"], exchange["response"]
        expected_request = _request(
            plan,
            selection,
            trace["model"]["name"],
            AgentBudget(**trace["budget"]),
        )
        model_event = model_events[0]
        if (
            request != expected_request
            or digest(request) != model_event["request_sha256"]
            or "format" in request
            or "tools" in request
        ):
            raise ValueError("Invalid complete-pair plain-text request")
        if response is not None:
            if not isinstance(response, dict) or digest(response) != model_event["response_sha256"]:
                raise ValueError("Invalid complete-pair raw response")
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            expected_content = content[:8000] if isinstance(content, str) else None
            try:
                expected_usage = _response_usage(response)
            except ValueError:
                expected_usage = (0, 0)
            if model_event["response_content"] != expected_content:
                raise ValueError("Complete-pair response content differs")
            if model_event["usage"] != {
                "prompt_tokens": expected_usage[0],
                "output_tokens": expected_usage[1],
            }:
                raise ValueError("Complete-pair response usage differs")
            action = model_event["action"]
            if action is not None:
                if (
                    response.get("model") != trace["model"]["name"]
                    or response.get("done") is not True
                    or response.get("done_reason") != "stop"
                    or not isinstance(message, dict)
                    or message.get("role") != "assistant"
                    or message.get("tool_calls")
                    or set(action)
                    != {"action", "tool_name", "arguments", "summary", "evidence_ids"}
                    or action["action"] != "finish"
                    or action["tool_name"] != ""
                    or action["arguments"] != {}
                    or action["summary"] != _plain_text(content)
                    or action["evidence_ids"] != [event["observation_id"]]
                ):
                    raise ValueError("Complete-pair model action differs from raw response")
    elif exchange != {"request": None, "response": None}:
        raise ValueError("Agent evidence-pair exchange exists without a model event")
    if result["protocol_status"] == "passed":
        observation_id = event["observation_id"]
        if (
            selection is None
            or selection["status"] != "complete"
            or len(model_events) != 1
            or trace["final"] is None
            or result["summary"] != trace["final"]["summary"]
            or result["evidence_ids"] != [observation_id]
            or trace["final"]["evidence_ids"] != [observation_id]
            or model_events[0]["action"] is None
            or model_events[0]["action"].get("summary") != result["summary"]
            or _plain_text(result["summary"]) != result["summary"]
        ):
            raise ValueError("Completed Agent evidence-pair summary is not selection-bound")
    elif result["summary"] is not None or result["evidence_ids"]:
        raise ValueError("Non-passed Agent evidence-pair result published an answer")
    return {
        "status": "passed",
        "result_id": result["result_id"],
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "protocol_status": result["protocol_status"],
        "evidence_completeness": result["evidence_completeness"]["status"],
        "semantic_assessment": result["semantic_assessment"],
        "model_calls": verification["model_calls"],
    }


def save_agent_evidence_pair_summary_result(
    report: Path, plan: dict[str, Any], result: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-pair summary output must be absent")
    verify_agent_evidence_pair_summary_result(report, plan, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_pair_summary_result(path: Path) -> dict[str, Any]:
    return read(path)
