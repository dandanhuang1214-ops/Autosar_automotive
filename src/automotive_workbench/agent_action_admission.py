"""Deterministic admission for control-plane action candidates.

The model may help prepare read-only evidence, but it does not decide whether a
safety-relevant candidate matches the requested action, capability, or facts.
"""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from automotive_workbench.agent_action_candidate import verify_action_candidate
from automotive_workbench.agent_approval import (
    build_agent_approval_request,
    verify_agent_approval_request,
)
from automotive_workbench.agent_proposal import (
    ActionCatalog,
    build_restricted_action_catalog,
)
from automotive_workbench.agent_runtime import verify_agent_checkpoint
from automotive_workbench.project_explanation import canonical, digest, read


ACTION_INTENT_VERSION = "agent-action-intent-0.1"
ACTION_ADMISSION_VERSION = "agent-action-admission-0.1"
ACTION_INTENT_BOUNDARY = (
    "This typed intent is issued by the Workbench control plane. It is not an "
    "operator identity, approval, or execution authorization."
)
ACTION_ADMISSION_BOUNDARY = (
    "The Workbench control plane deterministically checked the typed intent, "
    "capability, exact action, and evidence conditions. No model made or could "
    "override this admission decision, and no tool was invoked."
)
_DISPOSITIONS = {"exact_action", "no_action", "unsupported_action"}
_SCOPES = {"process_local_virtual", "host_socketcan", "hardware"}
_INTERFACES = {"virtual", "socketcan", "hardware"}


def _catalog_action(
    catalog: ActionCatalog, tool_name: str, arguments: Any
) -> dict[str, Any]:
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("Invalid Agent action intent tool name")
    checked = catalog.validate(tool_name, arguments)
    body = {
        "tool_name": tool_name,
        "permission": catalog.permission(tool_name),
        "arguments": checked,
    }
    return {**body, "call_id": digest(body)}


def _observation_results(checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for event in checkpoint["events"]:
        if event.get("kind") != "tool" or event.get("status") != "passed":
            continue
        observation_id = event.get("observation_id")
        result = event.get("result")
        if not isinstance(observation_id, str) or not isinstance(result, dict):
            continue
        if observation_id in results:
            raise ValueError("Duplicate Agent action intent observation")
        results[observation_id] = copy.deepcopy(result)
    return results


def _pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Invalid Agent action intent JSON pointer")
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ValueError("Agent action intent JSON pointer not found")
    return copy.deepcopy(current)


def _condition_actual(result: dict[str, Any], selector: Any) -> Any:
    if not isinstance(selector, dict) or set(selector) != {"kind", "value"}:
        raise ValueError("Invalid Agent action intent evidence selector")
    kind = selector.get("kind")
    value = selector.get("value")
    if kind == "pointer" and isinstance(value, str):
        return _pointer(result, value)
    if kind != "fact_id" or not isinstance(value, str):
        raise ValueError("Invalid Agent action intent evidence selector")
    matches = [
        fact.get("value")
        for fact in result.get("facts", [])
        if isinstance(fact, dict) and fact.get("fact_id") == value
    ]
    if len(matches) != 1:
        raise ValueError("Agent action intent fact selector must match once")
    return copy.deepcopy(matches[0])


def _conditions(
    checkpoint: dict[str, Any], value: Any
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Invalid Agent action intent evidence conditions")
    observations = _observation_results(checkpoint)
    checked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "observation_id",
            "selector",
            "expected_value",
        }:
            raise ValueError("Invalid Agent action intent evidence condition")
        observation_id = item.get("observation_id")
        selector = item.get("selector")
        selector_key = canonical(selector)
        if (
            not isinstance(observation_id, str)
            or observation_id not in observations
            or isinstance(item.get("expected_value"), (dict, list))
        ):
            raise ValueError("Invalid Agent action intent evidence condition")
        key = (observation_id, selector_key)
        if key in seen:
            raise ValueError("Invalid Agent action intent evidence condition")
        _condition_actual(observations[observation_id], selector)
        seen.add(key)
        checked.append(copy.deepcopy(item))
    return sorted(
        checked,
        key=lambda item: (item["observation_id"], canonical(item["selector"])),
    )


def _capability(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "scope",
        "interface",
        "channel",
    }:
        raise ValueError("Invalid Agent action intent capability")
    scope = value.get("scope")
    interface = value.get("interface")
    channel = value.get("channel")
    if (
        scope not in _SCOPES
        or interface not in _INTERFACES
        or (channel is not None and (not isinstance(channel, str) or not channel))
        or (scope == "process_local_virtual" and (interface != "virtual" or channel is not None))
        or (scope == "host_socketcan" and (interface != "socketcan" or channel is None))
        or (scope == "hardware" and (interface != "hardware" or channel is None))
    ):
        raise ValueError("Invalid Agent action intent capability")
    return copy.deepcopy(value)


def issue_action_intent(
    checkpoint: dict[str, Any],
    spec: dict[str, Any],
    catalog: ActionCatalog | None = None,
) -> dict[str, Any]:
    """Seal a typed action requirement without consulting a model."""
    verify_agent_checkpoint(checkpoint)
    if not isinstance(spec, dict) or set(spec) != {
        "disposition",
        "requested_capability",
        "requested_action",
        "evidence_conditions",
        "deterministic_decline_reason",
    }:
        raise ValueError("Invalid Agent action intent spec")
    action_catalog = catalog or build_restricted_action_catalog()
    disposition = spec.get("disposition")
    if disposition not in _DISPOSITIONS:
        raise ValueError("Invalid Agent action intent disposition")
    capability = _capability(spec.get("requested_capability"))
    conditions = _conditions(checkpoint, spec.get("evidence_conditions"))
    requested = spec.get("requested_action")
    reason = spec.get("deterministic_decline_reason")
    action = None
    if disposition == "exact_action":
        if (
            capability
            != {
                "scope": "process_local_virtual",
                "interface": "virtual",
                "channel": None,
            }
            or not isinstance(requested, dict)
            or set(requested) != {"tool_name", "arguments"}
            or not conditions
            or reason is not None
        ):
            raise ValueError("Invalid exact Agent action intent")
        action = _catalog_action(
            action_catalog, requested["tool_name"], requested["arguments"]
        )
    elif disposition == "no_action":
        if (
            capability is not None
            or requested is not None
            or conditions
            or reason != "action_not_required"
        ):
            raise ValueError("Invalid no-action Agent intent")
    elif (
        capability is None
        or capability["scope"] == "process_local_virtual"
        or requested is not None
        or reason != "outside_restricted_capabilities"
    ):
        raise ValueError("Invalid unsupported Agent action intent")
    body = {
        "schema_version": ACTION_INTENT_VERSION,
        "checkpoint_id": checkpoint["checkpoint_id"],
        "registry_binding_sha256": checkpoint["registry_binding_sha256"],
        "goal": checkpoint["goal"],
        "issued_by": "workbench-control-plane",
        "capability_binding_sha256": action_catalog.binding_sha256(),
        "disposition": disposition,
        "requested_capability": capability,
        "requested_action": action,
        "evidence_conditions": conditions,
        "deterministic_decline_reason": reason,
        "execution_authorized": False,
        "tool_invoked": False,
        "boundary": ACTION_INTENT_BOUNDARY,
    }
    return {"intent_id": digest(body), **body}


def verify_action_intent(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    catalog: ActionCatalog | None = None,
) -> dict[str, Any]:
    fields = {
        "intent_id",
        "schema_version",
        "checkpoint_id",
        "registry_binding_sha256",
        "goal",
        "issued_by",
        "capability_binding_sha256",
        "disposition",
        "requested_capability",
        "requested_action",
        "evidence_conditions",
        "deterministic_decline_reason",
        "execution_authorized",
        "tool_invoked",
        "boundary",
    }
    if not isinstance(intent, dict) or set(intent) != fields:
        raise ValueError("Invalid Agent action intent")
    action = intent.get("requested_action")
    if action is not None and not isinstance(action, dict):
        raise ValueError("Invalid Agent action intent")
    raw_action = (
        None
        if action is None
        else {"tool_name": action.get("tool_name"), "arguments": action.get("arguments")}
    )
    expected = issue_action_intent(
        checkpoint,
        {
            "disposition": intent.get("disposition"),
            "requested_capability": intent.get("requested_capability"),
            "requested_action": raw_action,
            "evidence_conditions": intent.get("evidence_conditions"),
            "deterministic_decline_reason": intent.get(
                "deterministic_decline_reason"
            ),
        },
        catalog,
    )
    if intent != expected:
        raise ValueError("Agent action intent differs from typed content")
    return {
        "status": "passed",
        "intent_id": intent["intent_id"],
        "disposition": intent["disposition"],
        "execution_authorized": False,
        "tool_invoked": False,
    }


def _checked_candidates(
    checkpoint: dict[str, Any],
    candidates: list[dict[str, Any]],
    catalog: ActionCatalog,
) -> list[dict[str, Any]]:
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Agent action admission requires candidates")
    checked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        verify_action_candidate(checkpoint, candidate, catalog)
        candidate_id = candidate["candidate_id"]
        if candidate_id in seen:
            raise ValueError("Duplicate Agent action admission candidate")
        seen.add(candidate_id)
        checked.append(copy.deepcopy(candidate))
    return sorted(checked, key=lambda item: item["candidate_id"])


def admit_action_candidates(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    catalog: ActionCatalog | None = None,
) -> dict[str, Any]:
    """Apply deterministic applicability rules without a model call."""
    verify_agent_checkpoint(checkpoint)
    action_catalog = catalog or build_restricted_action_catalog()
    verify_action_intent(checkpoint, intent, action_catalog)
    checked = _checked_candidates(checkpoint, candidates, action_catalog)
    observations = _observation_results(checkpoint)
    evaluated = [
        {
            **copy.deepcopy(condition),
            "actual_value": _condition_actual(
                observations[condition["observation_id"]], condition["selector"]
            ),
            "matched": _condition_actual(
                observations[condition["observation_id"]], condition["selector"]
            )
            == condition["expected_value"],
        }
        for condition in intent["evidence_conditions"]
    ]
    status = "declined"
    selected_id = None
    requested_action = None
    eligible: list[str] = []
    if intent["disposition"] == "no_action":
        reason = "control_plane_declined:action_not_required"
    elif intent["disposition"] == "unsupported_action":
        reason = "control_plane_declined:outside_restricted_capabilities"
    elif not all(item["matched"] for item in evaluated):
        reason = "control_plane_declined:insufficient_evidence"
    else:
        condition_observations = {
            item["observation_id"] for item in intent["evidence_conditions"]
        }
        eligible = [
            candidate["candidate_id"]
            for candidate in checked
            if candidate["action"] == intent["requested_action"]
            and condition_observations <= set(candidate["evidence_ids"])
        ]
        if len(eligible) == 1:
            status = "approval_required"
            reason = "control_plane_exact_candidate_admitted"
            selected_id = eligible[0]
            requested_action = copy.deepcopy(intent["requested_action"])
        elif eligible:
            status = "refused"
            reason = "ambiguous_exact_applicable_candidate"
        else:
            status = "refused"
            reason = "no_exact_applicable_candidate"
    evidence_ids = sorted(
        {item["observation_id"] for item in intent["evidence_conditions"]}
    )
    body = {
        "schema_version": ACTION_ADMISSION_VERSION,
        "status": status,
        "reason": reason,
        "checkpoint_id": checkpoint["checkpoint_id"],
        "registry_binding_sha256": checkpoint["registry_binding_sha256"],
        "goal": checkpoint["goal"],
        "intent_id": intent["intent_id"],
        "candidate_ids": [item["candidate_id"] for item in checked],
        "candidate_set_sha256": digest(checked),
        "evaluated_conditions": evaluated,
        "eligible_candidate_ids": eligible,
        "selected_candidate_id": selected_id,
        "requested_action": requested_action,
        "evidence_ids": evidence_ids,
        "model_invoked": False,
        "execution_authorized": False,
        "tool_invoked": False,
        "boundary": ACTION_ADMISSION_BOUNDARY,
    }
    return {"admission_id": digest(body), **body}


def verify_action_admission(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    admission: dict[str, Any],
    catalog: ActionCatalog | None = None,
) -> dict[str, Any]:
    expected = admit_action_candidates(checkpoint, intent, candidates, catalog)
    if admission != expected:
        raise ValueError("Agent action admission differs from deterministic result")
    return {
        "status": "passed",
        "admission_id": admission["admission_id"],
        "admission_status": admission["status"],
        "candidate_id": admission["selected_candidate_id"],
        "requested_action": copy.deepcopy(admission["requested_action"]),
        "model_invoked": False,
        "execution_authorized": False,
        "tool_invoked": False,
    }


def build_approval_request_from_admission(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    admission: dict[str, Any],
    *,
    reason: str,
    created_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    verified = verify_action_admission(checkpoint, intent, candidates, admission)
    if verified["admission_status"] != "approval_required":
        raise ValueError("Only an admitted exact action can become a request")
    action = verified["requested_action"]
    request = build_agent_approval_request(
        checkpoint,
        tool_name=action["tool_name"],
        permission=action["permission"],
        arguments=action["arguments"],
        reason=reason,
        evidence_ids=admission["evidence_ids"],
        created_at=created_at,
        expires_at=expires_at,
    )
    if request["requested_action"] != action:
        raise ValueError("Approval request differs from admitted action")
    return request


def verify_approval_request_from_admission(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    admission: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    verified = verify_action_admission(checkpoint, intent, candidates, admission)
    if verified["admission_status"] != "approval_required":
        raise ValueError("Only an admitted exact action can bind approval")
    verify_agent_approval_request(checkpoint, request)
    if (
        request["requested_action"] != verified["requested_action"]
        or request["evidence_ids"] != admission["evidence_ids"]
    ):
        raise ValueError("Approval request differs from admitted action")
    return {
        "status": "passed",
        "admission_id": admission["admission_id"],
        "candidate_id": admission["selected_candidate_id"],
        "request_id": request["request_id"],
        "requested_action": copy.deepcopy(request["requested_action"]),
        "model_invoked": False,
        "execution_authorized": False,
        "tool_invoked": False,
    }


def _save(value: dict[str, Any], output: Path, name: str) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError(f"Agent action {name} output must be absent")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(value) + "\n", encoding="utf-8", newline="\n")
    return value


def save_action_intent(
    checkpoint: dict[str, Any], intent: dict[str, Any], output: Path
) -> dict[str, Any]:
    verify_action_intent(checkpoint, intent)
    return _save(intent, output, "intent")


def save_action_admission(
    checkpoint: dict[str, Any],
    intent: dict[str, Any],
    candidates: list[dict[str, Any]],
    admission: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    verify_action_admission(checkpoint, intent, candidates, admission)
    return _save(admission, output, "admission")


def load_and_verify_action_intent(
    checkpoint_path: Path, intent_path: Path
) -> dict[str, Any]:
    return verify_action_intent(read(checkpoint_path), read(intent_path))


def load_and_verify_action_admission(
    checkpoint_path: Path,
    intent_path: Path,
    candidate_paths: list[Path],
    admission_path: Path,
) -> dict[str, Any]:
    return verify_action_admission(
        read(checkpoint_path),
        read(intent_path),
        [read(path) for path in candidate_paths],
        read(admission_path),
    )
