"""Plain-text evidence summaries over immutable 0.1 control-plane read plans."""
from __future__ import annotations

import copy
from pathlib import Path
import time
from typing import Any, Callable

from automotive_workbench.agent_evidence_plan import verify_agent_evidence_plan
from automotive_workbench.agent_runtime import (
    AgentBudget,
    BOUNDARY as TRACE_BOUNDARY,
    ToolRegistry,
    verify_agent_trace,
)
from automotive_workbench.explanation_services import ServiceError
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import canonical, digest, read

RESULT_VERSION = "agent-evidence-summary-result-0.2"
MODEL_INTERFACE = "ollama-plain-text-summary-0.2"
RESULT_BOUNDARY = (
    "The immutable 0.1 evidence plan still fixes every read. The 0.2 model interface "
    "accepts one bounded plain-text summary; the control plane owns the result envelope, "
    "status, complete observation citations, and offline verification. Model prose remains "
    "unassessed and cannot change engineering status or prove an external action."
)
SYNTHESIS_PROMPT = """Summarize only the control-plane-selected evidence for the stated goal.
Return plain text only: no JSON, YAML, XML, Markdown fences, tool calls, or citation IDs.
State recorded statuses and reasons exactly. Separate project records from reviewed source
material, label hypotheses as unproven, and state important evidence limits. Do not claim
that a command, vendor tool, configuration write, bus access, or hardware action occurred
unless an observation explicitly records it. The control plane attaches all citations."""


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
    if (
        type(prompt) is not int
        or type(output) is not int
        or prompt < 0
        or output < 0
    ):
        raise ValueError("invalid_model_usage")
    return prompt, output


def _trace(
    plan: dict[str, Any],
    registry: ToolRegistry,
    client: ModelClient,
    model: str,
    budget: AgentBudget,
    clock: Callable[[], float],
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_agent_evidence_plan(plan)
    if not isinstance(model, str) or not model:
        raise ValueError("Agent evidence-summary model must be nonempty")
    manifest = registry.manifest()
    available = {item["name"] for item in manifest}
    if any(step["tool_name"] not in available for step in plan["steps"]):
        raise ValueError("Agent evidence-summary tool is unavailable in the bound registry")
    if len(plan["steps"]) > budget.max_tool_calls:
        raise ValueError("Agent evidence summary exceeds the tool-call budget")
    if len(plan["steps"]) + 1 > budget.max_steps:
        raise ValueError("Agent evidence summary exceeds the step budget")
    if budget.max_model_calls < 1:
        raise ValueError("Agent evidence summary requires one model call")
    if not (client.capabilities.identity_pinning and client.capabilities.usage_metrics):
        raise ValueError("Model client lacks evidence-summary identity or usage support")

    started = clock()
    events: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    status = "blocked"
    reason = "model_unavailable"
    final: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    service_version: str | None = None
    prompt_tokens = output_tokens = model_calls = tool_calls = 0
    exchange: dict[str, Any] = {"request": None, "response": None}

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
                    "refused" if error.startswith("agent_knowledge_denied:") else "blocked"
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
                max_output_tokens = min(budget.max_output_tokens_per_call, remaining)
                request = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0,
                        "seed": 0,
                        "num_ctx": budget.context_window,
                        "num_predict": max_output_tokens,
                    },
                    "keep_alive": "2m",
                }
                exchange["request"] = copy.deepcopy(request)
                action: dict[str, Any] | None = None
                action_error: str | None = None
                response_sha256: str | None = None
                response_content: str | None = None
                usage = {"prompt_tokens": 0, "output_tokens": 0}
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
                        usage = {
                            "prompt_tokens": prompt_tokens,
                            "output_tokens": output_tokens,
                        }
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
                    if prompt_tokens + output_tokens > budget.context_window:
                        raise ValueError("invalid_or_exceeded_context_budget")
                    summary = _plain_text(response["message"]["content"])
                    action = {
                        "action": "finish",
                        "tool_name": "",
                        "arguments": {},
                        "summary": summary,
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
                    status, reason = "blocked", action_error or "invalid_plain_text_summary"
                elif client.identity(model) != identity:
                    status, reason = "refused", "model_identity_changed"
                elif elapsed() > budget.max_seconds:
                    status, reason = "refused", "wall_clock_budget_exhausted"
                elif output_tokens > max_output_tokens:
                    status, reason = "refused", "model_output_token_budget_exhausted"
                elif prompt_tokens + output_tokens > budget.max_total_tokens:
                    status, reason = "refused", "token_budget_exhausted"
                else:
                    final = {
                        "summary": action["summary"],
                        "evidence_ids": action["evidence_ids"],
                        "semantic_status": "unassessed",
                    }
                    status = "passed"
                    reason = "completed_with_control_plane_plain_text_summary"
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
    return trace, exchange


def run_agent_evidence_summary(
    plan: dict[str, Any],
    registry: ToolRegistry,
    client: ModelClient,
    model: str,
    budget: AgentBudget | None = None,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    trace, exchange = _trace(
        plan,
        registry,
        client,
        model,
        budget
        or AgentBudget(
            max_steps=3,
            max_model_calls=1,
            max_tool_calls=2,
            max_output_tokens_per_call=512,
        ),
        clock,
    )
    final = trace["final"]
    body = {
        "artifact_type": "agent-evidence-summary-result",
        "schema_version": RESULT_VERSION,
        "model_interface": MODEL_INTERFACE,
        "status": trace["status"],
        "semantic_status": "unassessed",
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "summary": final["summary"] if final is not None else None,
        "evidence_ids": final["evidence_ids"] if final is not None else [],
        "model_exchange": exchange,
        "trace": trace,
        "boundary": RESULT_BOUNDARY,
    }
    result = {"result_id": digest(body), **body}
    verify_agent_evidence_summary_result(plan, result)
    return result


def verify_agent_evidence_summary_result(
    plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_evidence_plan(plan)
    fields = {
        "result_id",
        "artifact_type",
        "schema_version",
        "model_interface",
        "status",
        "semantic_status",
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
        or result["artifact_type"] != "agent-evidence-summary-result"
        or result["schema_version"] != RESULT_VERSION
        or result["model_interface"] != MODEL_INTERFACE
        or result["status"] not in {"passed", "refused", "blocked"}
        or result["semantic_status"] != "unassessed"
        or result["plan_id"] != plan["plan_id"]
        or result["boundary"] != RESULT_BOUNDARY
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
    ):
        raise ValueError("Invalid Agent evidence-summary result")
    trace = result["trace"]
    verification = verify_agent_trace(trace)
    if (
        result["trace_id"] != trace["trace_id"]
        or result["status"] != trace["status"]
        or trace["goal"] != plan["goal"]
    ):
        raise ValueError("Agent evidence-summary result differs from its trace")
    tool_events = [event for event in trace["events"] if event["kind"] == "tool"]
    model_events = [event for event in trace["events"] if event["kind"] == "model"]
    actual_steps = [
        {"tool_name": event["tool_name"], "arguments": event["arguments"]}
        for event in tool_events
    ]
    if actual_steps != plan["steps"][: len(actual_steps)]:
        raise ValueError("Agent evidence-summary trace changed the planned read steps")
    if len(model_events) > 1:
        raise ValueError("Agent evidence summary may make at most one model call")
    if model_events and (
        actual_steps != plan["steps"]
        or any(event["status"] != "passed" for event in tool_events)
        or [event["kind"] for event in trace["events"]]
        != ["tool"] * len(plan["steps"]) + ["model"]
    ):
        raise ValueError("Agent evidence-summary model call did not follow planned reads")
    exchange = result["model_exchange"]
    if not isinstance(exchange, dict) or set(exchange) != {"request", "response"}:
        raise ValueError("Invalid Agent evidence-summary model exchange")
    request, response = exchange["request"], exchange["response"]
    if model_events:
        event = model_events[0]
        observations = [
            {
                "observation_id": tool_event["observation_id"],
                "tool_name": tool_event["tool_name"],
                "result": tool_event["model_projection"],
            }
            for tool_event in tool_events
        ]
        expected_context = {
            "goal": plan["goal"],
            "plan_id": plan["plan_id"],
            "scope": plan["scope"],
            "observations": observations,
            "boundary": RESULT_BOUNDARY,
        }
        expected_request = {
            "model": trace["model"]["name"],
            "messages": [
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {"role": "user", "content": canonical(expected_context)},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "seed": 0,
                "num_ctx": trace["budget"]["context_window"],
                "num_predict": min(
                    trace["budget"]["max_output_tokens_per_call"],
                    trace["budget"]["max_total_tokens"],
                ),
            },
            "keep_alive": "2m",
        }
        if (
            not isinstance(request, dict)
            or canonical(request) != canonical(expected_request)
            or digest(request) != event["request_sha256"]
            or "format" in request
            or "tools" in request
            or request.get("stream") is not False
            or request.get("think") is not False
            or not isinstance(request.get("messages"), list)
            or not request["messages"]
            or request["messages"][0] != {"role": "system", "content": SYNTHESIS_PROMPT}
        ):
            raise ValueError("Invalid Agent evidence-summary plain-text request")
        if response is None:
            if (
                event["response_sha256"] is not None
                or event["response_content"] is not None
                or event["usage"] != {"prompt_tokens": 0, "output_tokens": 0}
            ):
                raise ValueError("Agent evidence-summary response record differs")
        else:
            if not isinstance(response, dict):
                raise ValueError("Agent evidence-summary response record differs")
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            expected_content = content[:8000] if isinstance(content, str) else None
            try:
                expected_usage = _response_usage(response)
            except ValueError:
                expected_usage = (0, 0)
            if (
                digest(response) != event["response_sha256"]
                or expected_content != event["response_content"]
                or event["usage"]
                != {
                    "prompt_tokens": expected_usage[0],
                    "output_tokens": expected_usage[1],
                }
            ):
                raise ValueError("Agent evidence-summary response record differs")
    elif request is not None or response is not None:
        raise ValueError("Agent evidence-summary recorded an uncalled model exchange")
    if trace["status"] == "passed":
        observations = [event["observation_id"] for event in tool_events]
        action = model_events[0]["action"] if model_events else None
        response = exchange["response"]
        response_message = response.get("message") if isinstance(response, dict) else None
        model_event = model_events[0] if model_events else None
        if (
            actual_steps != plan["steps"]
            or len(model_events) != 1
            or trace["final"] is None
            or action is None
            or set(action)
            != {"action", "tool_name", "arguments", "summary", "evidence_ids"}
            or action.get("action") != "finish"
            or action.get("tool_name") != ""
            or action.get("arguments") != {}
            or result["summary"] != trace["final"]["summary"]
            or result["summary"] != action.get("summary")
            or result["evidence_ids"] != observations
            or trace["final"]["evidence_ids"] != observations
            or action.get("evidence_ids") != observations
            or result["summary"] != _plain_text(result["summary"])
            or not isinstance(response, dict)
            or response.get("model") != trace["model"]["name"]
            or response.get("done") is not True
            or response.get("done_reason") != "stop"
            or not isinstance(response_message, dict)
            or response_message.get("role") != "assistant"
            or response_message.get("tool_calls")
            or result["summary"] != _plain_text(response_message.get("content"))
            or model_event is None
            or _response_usage(response)
            != (
                model_event["usage"]["prompt_tokens"],
                model_event["usage"]["output_tokens"],
            )
            or _response_usage(response)[1]
            > request["options"]["num_predict"]
            or sum(_response_usage(response)) > trace["budget"]["context_window"]
        ):
            raise ValueError("Completed Agent evidence-summary result is not plan-bound")
    elif result["summary"] is not None or result["evidence_ids"] != []:
        raise ValueError("Incomplete Agent evidence-summary result published an answer")
    return {
        "status": "passed",
        "result_id": result["result_id"],
        "plan_id": plan["plan_id"],
        "trace_id": trace["trace_id"],
        "agent_status": verification["agent_status"],
        "model_interface": MODEL_INTERFACE,
        "planned_tools": len(plan["steps"]),
        "cited_observations": len(result["evidence_ids"]),
        "semantic_status": "unassessed",
    }


def save_agent_evidence_summary_result(
    plan: dict[str, Any], result: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evidence-summary result output must be absent")
    verify_agent_evidence_summary_result(plan, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def load_agent_evidence_summary_result(path: Path) -> dict[str, Any]:
    value = read(path)
    if not isinstance(value, dict):
        raise ValueError("Agent evidence-summary result must be an object")
    return value
