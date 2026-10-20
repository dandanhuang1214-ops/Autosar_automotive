"""Deterministic read-tool plans followed by one evidence-bound model summary."""
from __future__ import annotations

import copy
from pathlib import Path
import time
from typing import Any, Callable

from automotive_workbench.agent_runtime import (
    AgentBudget,
    BOUNDARY as TRACE_BOUNDARY,
    ToolRegistry,
    verify_agent_trace,
)
from automotive_workbench.explanation_services import ServiceError, parse_json
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import canonical, digest, read

PLAN_VERSION = "agent-evidence-plan-0.1"
RESULT_VERSION = "agent-evidence-plan-result-0.1"
PLAN_BOUNDARY = (
    "The control plane selects a fixed sequence of registered read tools. The model "
    "cannot add, remove, reorder, or parameterize those calls."
)
RESULT_BOUNDARY = (
    "Read observations and their citations are fixed by the control plane. The model "
    "produces one unassessed summary and cannot change engineering status or evidence."
)
SYNTHESIS_PROMPT = """You summarize control-plane-selected read evidence.
Return exactly the requested JSON object. Answer the goal completely using only the
provided observations. State recorded statuses and reasons precisely, distinguish
documented facts from hypotheses, and state what the evidence cannot prove. Do not claim
that a command, vendor tool, configuration write, bus access, or hardware action occurred
unless an observation explicitly records it. Citations are attached by the control plane;
do not invent identifiers."""

_SCOPES: dict[str, tuple[str, ...]] = {
    "project_detail": ("project_query_facts",),
    "reviewed_knowledge": ("knowledge_retrieve_reviewed",),
    "project_and_reviewed_knowledge": (
        "project_query_facts",
        "knowledge_retrieve_reviewed",
    ),
}


def _event(previous: str | None, sequence: int, body: dict[str, Any]) -> dict[str, Any]:
    value = {"sequence": sequence, "previous_event_id": previous, **body}
    return {"event_id": digest(value), **value}


def _plan_body(goal: str, scope: str) -> dict[str, Any]:
    if not isinstance(goal, str) or not 0 < len(goal.strip()) <= 2000:
        raise ValueError("Agent evidence-plan goal must contain 1..2000 characters")
    if scope not in _SCOPES:
        raise ValueError("Unsupported Agent evidence-plan scope")
    normalized = goal.strip()
    return {
        "artifact_type": "agent-evidence-plan",
        "schema_version": PLAN_VERSION,
        "scope": scope,
        "goal": normalized,
        "steps": [
            {"tool_name": name, "arguments": {"question": normalized}}
            for name in _SCOPES[scope]
        ],
        "boundary": PLAN_BOUNDARY,
    }


def build_agent_evidence_plan(goal: str, scope: str) -> dict[str, Any]:
    body = _plan_body(goal, scope)
    return {"plan_id": digest(body), **body}


def verify_agent_evidence_plan(plan: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "plan_id",
        "artifact_type",
        "schema_version",
        "scope",
        "goal",
        "steps",
        "boundary",
    }
    if not isinstance(plan, dict) or set(plan) != fields:
        raise ValueError("Invalid Agent evidence-plan fields")
    goal = plan.get("goal")
    scope = plan.get("scope")
    if not isinstance(goal, str) or not isinstance(scope, str):
        raise ValueError("Invalid Agent evidence-plan metadata")
    expected = build_agent_evidence_plan(goal, scope)
    if canonical(plan) != canonical(expected):
        raise ValueError("Agent evidence plan differs from its deterministic scope")
    return {
        "status": "passed",
        "plan_id": plan["plan_id"],
        "scope": plan["scope"],
        "step_count": len(plan["steps"]),
    }


def save_agent_evidence_plan(plan: dict[str, Any], output: Path) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-plan output must be absent")
    verify_agent_evidence_plan(plan)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(plan) + "\n", encoding="utf-8", newline="\n")
    return plan


def _trace(
    plan: dict[str, Any],
    registry: ToolRegistry,
    client: ModelClient,
    model: str,
    budget: AgentBudget,
    clock: Callable[[], float],
) -> dict[str, Any]:
    verify_agent_evidence_plan(plan)
    if not isinstance(model, str) or not model:
        raise ValueError("Agent evidence-plan model must be nonempty")
    manifest = registry.manifest()
    available = {item["name"] for item in manifest}
    if any(step["tool_name"] not in available for step in plan["steps"]):
        raise ValueError("Agent evidence-plan tool is unavailable in the bound registry")
    if len(plan["steps"]) > budget.max_tool_calls:
        raise ValueError("Agent evidence plan exceeds the tool-call budget")
    capabilities = client.capabilities
    if not (
        capabilities.structured_output
        and capabilities.identity_pinning
        and capabilities.usage_metrics
    ):
        raise ValueError("Model client lacks planned explanation capabilities")

    started = clock()
    events: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    status = "blocked"
    reason = "model_unavailable"
    final: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    service_version: str | None = None
    prompt_tokens = output_tokens = model_calls = tool_calls = 0

    def elapsed() -> float:
        return max(0.0, clock() - started)

    try:
        service_version = client.service_version()
        identity = client.identity(model)
        if not isinstance(identity, dict):
            raise ServiceError("invalid_model_identity")
        for step in plan["steps"]:
            if elapsed() > budget.max_seconds:
                status, reason = "refused", "wall_clock_budget_exhausted"
                break
            tool_name = step["tool_name"]
            arguments = copy.deepcopy(step["arguments"])
            call_id = digest({"tool_name": tool_name, "arguments": arguments})
            tool_result: dict[str, Any] | None = None
            projection: dict[str, Any] | None = None
            error: str | None = None
            failure_status = "refused"
            try:
                tool_result = registry.invoke(tool_name, arguments)
                if len(canonical(tool_result)) > budget.max_observation_chars:
                    raise ValueError("Agent tool result exceeds observation budget")
                projection = registry.project(tool_name, tool_result)
                if len(canonical(projection)) > budget.max_observation_chars:
                    raise ValueError("Agent tool projection exceeds observation budget")
            except ServiceError as exc:
                error = str(exc)
                failure_status = (
                    "refused"
                    if error.startswith("agent_knowledge_denied:")
                    else "blocked"
                )
            except OSError as exc:
                error = str(exc)
                failure_status = "blocked"
            except (ValueError, TypeError, KeyError) as exc:
                error = str(exc)
            tool_calls += 1
            observation_id = (
                digest(
                    {
                        "call_id": call_id,
                        "result_sha256": digest(tool_result),
                        "projection_sha256": digest(projection),
                    }
                )
                if tool_result is not None and projection is not None
                else None
            )
            events.append(
                _event(
                    events[-1]["event_id"] if events else None,
                    len(events) + 1,
                    {
                        "kind": "tool",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "call_id": call_id,
                        "status": "passed" if observation_id is not None else failure_status,
                        "result": tool_result,
                        "result_sha256": digest(tool_result) if tool_result is not None else None,
                        "model_projection": projection,
                        "projection_sha256": digest(projection) if projection is not None else None,
                        "observation_id": observation_id,
                        "error": error,
                    },
                )
            )
            if observation_id is None or projection is None:
                status, reason = failure_status, error or "tool_failed"
                break
            observations.append(
                {
                    "observation_id": observation_id,
                    "tool_name": tool_name,
                    "result": projection,
                }
            )
        else:
            remaining = budget.max_total_tokens
            if elapsed() > budget.max_seconds:
                status, reason = "refused", "wall_clock_budget_exhausted"
            elif remaining < 1:
                status, reason = "refused", "token_budget_exhausted"
            else:
                context = {
                    "goal": plan["goal"],
                    "plan_id": plan["plan_id"],
                    "scope": plan["scope"],
                    "observations": observations,
                    "boundary": RESULT_BOUNDARY,
                }
                messages = [
                    {"role": "system", "content": SYNTHESIS_PROMPT},
                    {"role": "user", "content": canonical(context)},
                ]
                schema = {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["summary"],
                    "properties": {
                        "summary": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 1000,
                        }
                    },
                }
                max_output_tokens = min(
                    budget.max_output_tokens_per_call, remaining
                )
                request = {
                    "model": model,
                    "messages": messages,
                    "schema": schema,
                    "max_output_tokens": max_output_tokens,
                    "context_window": budget.context_window,
                }
                action: dict[str, Any] | None = None
                action_error: str | None = None
                response_sha256: str | None = None
                response_content: str | None = None
                usage = {"prompt_tokens": 0, "output_tokens": 0}
                try:
                    completion = client.complete_structured(
                        model=model,
                        messages=messages,
                        schema=schema,
                        max_output_tokens=max_output_tokens,
                        context_window=budget.context_window,
                    )
                    model_calls = 1
                    prompt_tokens = completion.input_tokens
                    output_tokens = completion.output_tokens
                    usage = {
                        "prompt_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                    }
                    response_sha256 = digest(completion.raw)
                    response_content = completion.content
                    decoded = parse_json(completion.content)
                    if (
                        not isinstance(decoded, dict)
                        or set(decoded) != {"summary"}
                        or not isinstance(decoded["summary"], str)
                        or not 0 < len(decoded["summary"]) <= 1000
                    ):
                        raise ValueError("Invalid planned Agent summary")
                    action = {
                        "action": "finish",
                        "tool_name": "",
                        "arguments": {},
                        "summary": decoded["summary"],
                        "evidence_ids": [
                            item["observation_id"] for item in observations
                        ],
                    }
                except (OSError, ValueError, TypeError, KeyError, ServiceError) as exc:
                    if model_calls == 0:
                        model_calls = 1
                    action_error = str(exc)
                events.append(
                    _event(
                        events[-1]["event_id"] if events else None,
                        len(events) + 1,
                        {
                            "kind": "model",
                            "request_sha256": digest(request),
                            "response_sha256": response_sha256,
                            "response_content": response_content,
                            "usage": usage,
                            "action": action,
                            "error": action_error,
                        },
                    )
                )
                if action is None:
                    status, reason = "blocked", action_error or "invalid_model_summary"
                elif client.identity(model) != identity:
                    status, reason = "refused", "model_identity_changed"
                elif elapsed() > budget.max_seconds:
                    status, reason = "refused", "wall_clock_budget_exhausted"
                elif prompt_tokens + output_tokens > budget.max_total_tokens:
                    status, reason = "refused", "token_budget_exhausted"
                else:
                    final = {
                        "summary": action["summary"],
                        "evidence_ids": action["evidence_ids"],
                        "semantic_status": "unassessed",
                    }
                    status = "passed"
                    reason = "completed_with_control_plane_evidence_plan"
    except (OSError, ValueError, TypeError, KeyError, ServiceError) as exc:
        status, reason = "blocked", str(exc)

    body = {
        "schema_version": "readonly-agent-trace-0.1",
        "status": status,
        "reason": reason,
        "semantic_status": "unassessed",
        "goal": plan["goal"],
        "model": identity,
        "service_version": service_version,
        "tool_manifest": manifest,
        "budget": budget.as_dict(),
        "usage": {
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": prompt_tokens + output_tokens,
            "elapsed_ms": round(elapsed() * 1000, 3),
        },
        "events": events,
        "final": final,
        "boundary": TRACE_BOUNDARY,
    }
    trace = {"trace_id": digest(body), **body}
    verify_agent_trace(trace)
    return trace


def run_agent_evidence_plan(
    plan: dict[str, Any],
    registry: ToolRegistry,
    client: ModelClient,
    model: str,
    budget: AgentBudget | None = None,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    trace = _trace(plan, registry, client, model, budget or AgentBudget(), clock)
    body = {
        "artifact_type": "agent-evidence-plan-result",
        "schema_version": RESULT_VERSION,
        "status": trace["status"],
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "trace": trace,
        "boundary": RESULT_BOUNDARY,
    }
    result = {"result_id": digest(body), **body}
    verify_agent_evidence_plan_result(plan, result)
    return result


def verify_agent_evidence_plan_result(
    plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_evidence_plan(plan)
    fields = {
        "result_id",
        "artifact_type",
        "schema_version",
        "status",
        "plan_id",
        "trace_id",
        "trace",
        "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result["artifact_type"] != "agent-evidence-plan-result"
        or result["schema_version"] != RESULT_VERSION
        or result["status"] not in {"passed", "refused", "blocked"}
        or result["boundary"] != RESULT_BOUNDARY
        or result["plan_id"] != plan["plan_id"]
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
    ):
        raise ValueError("Invalid Agent evidence-plan result")
    trace = result["trace"]
    verification = verify_agent_trace(trace)
    if (
        result["trace_id"] != trace["trace_id"]
        or result["status"] != trace["status"]
        or trace["goal"] != plan["goal"]
    ):
        raise ValueError("Agent evidence-plan result differs from its trace")
    tool_events = [event for event in trace["events"] if event["kind"] == "tool"]
    model_events = [event for event in trace["events"] if event["kind"] == "model"]
    actual_steps = [
        {"tool_name": event["tool_name"], "arguments": event["arguments"]}
        for event in tool_events
    ]
    if actual_steps != plan["steps"][: len(actual_steps)]:
        raise ValueError("Agent evidence-plan trace changed the planned read steps")
    if len(model_events) > 1:
        raise ValueError("Agent evidence plan may make at most one model call")
    if model_events and (
        actual_steps != plan["steps"]
        or any(event["status"] != "passed" for event in tool_events)
        or [event["kind"] for event in trace["events"]]
        != ["tool"] * len(plan["steps"]) + ["model"]
    ):
        raise ValueError("Agent evidence-plan model call did not follow all planned reads")
    if trace["status"] == "passed":
        observations = [event["observation_id"] for event in tool_events]
        if (
            actual_steps != plan["steps"]
            or len(model_events) != 1
            or trace["final"] is None
            or trace["final"]["evidence_ids"] != observations
            or model_events[0].get("action") is None
            or model_events[0]["action"].get("action") != "finish"
        ):
            raise ValueError("Completed Agent evidence-plan result is not plan-bound")
    return {
        "status": "passed",
        "result_id": result["result_id"],
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "agent_status": verification["agent_status"],
        "planned_tools": len(plan["steps"]),
        "cited_observations": (
            len(trace["final"]["evidence_ids"])
            if trace["final"] is not None
            else 0
        ),
    }


def save_agent_evidence_plan_result(
    plan: dict[str, Any], result: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-plan result output must be absent")
    verify_agent_evidence_plan_result(plan, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_plan(path: Path) -> dict[str, Any]:
    plan = read(path)
    verify_agent_evidence_plan(plan)
    return plan
