"""Offline-verifiable approval records for paused Agent work.

Approval decisions deliberately do not execute or authorize a side effect. A future
execution protocol must consume an approved decision with its own authenticated,
one-shot transaction record before non-read tools can be registered.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.agent_runtime import verify_agent_checkpoint
from automotive_workbench.project_explanation import canonical, digest, read


APPROVAL_REQUEST_VERSION = "readonly-agent-approval-request-0.1"
APPROVAL_DECISION_VERSION = "readonly-agent-approval-decision-0.1"
APPROVAL_BOUNDARY = (
    "This artifact records a local approval state only. It does not authenticate "
    "the operator, execute a tool, or authorize a side effect."
)
APPROVAL_PERMISSIONS = {"execute", "write", "hardware"}
APPROVAL_STATES = {"approved", "denied", "expired"}
MAX_APPROVAL_SECONDS = 86_400
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")


def _timestamp(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"Agent approval {name} requires a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Invalid Agent approval {name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid Agent approval {name}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Agent approval {name} requires a timezone")
    return parsed.astimezone(timezone.utc)


def _observations(checkpoint: dict[str, Any]) -> set[str]:
    return {
        event["observation_id"]
        for event in checkpoint["events"]
        if event.get("kind") == "tool"
        and event.get("status") == "passed"
        and isinstance(event.get("observation_id"), str)
    }


def _validate_action(action: Any) -> None:
    if (
        not isinstance(action, dict)
        or set(action)
        != {"tool_name", "permission", "arguments", "call_id"}
        or not isinstance(action.get("tool_name"), str)
        or _TOOL_NAME.fullmatch(action["tool_name"]) is None
        or action.get("permission") not in APPROVAL_PERMISSIONS
        or not isinstance(action.get("arguments"), dict)
        or len(canonical(action["arguments"])) > 20_000
        or action.get("call_id")
        != digest(
            {
                "tool_name": action.get("tool_name"),
                "permission": action.get("permission"),
                "arguments": action.get("arguments"),
            }
        )
    ):
        raise ValueError("Invalid Agent approval action")


def build_agent_approval_request(
    checkpoint: dict[str, Any],
    *,
    tool_name: str,
    permission: str,
    arguments: dict[str, Any],
    reason: str,
    evidence_ids: list[str],
    created_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Build a pending request bound to one checkpoint and exact proposed call."""
    verify_agent_checkpoint(checkpoint)
    action = {
        "tool_name": tool_name,
        "permission": permission,
        "arguments": copy.deepcopy(arguments),
        "call_id": digest(
            {
                "tool_name": tool_name,
                "permission": permission,
                "arguments": arguments,
            }
        ),
    }
    _validate_action(action)
    if tool_name in {tool["name"] for tool in checkpoint["tool_manifest"]}:
        raise ValueError("Registered read tools do not require Agent approval")
    if (
        not isinstance(reason, str)
        or not 0 < len(reason.strip()) <= 1000
        or not isinstance(evidence_ids, list)
        or not evidence_ids
        or len(evidence_ids) != len(set(evidence_ids))
        or not set(evidence_ids) <= _observations(checkpoint)
    ):
        raise ValueError("Invalid Agent approval justification")
    created = _parse_timestamp(_timestamp(created_at, "created_at"), "created_at")
    expires = _parse_timestamp(_timestamp(expires_at, "expires_at"), "expires_at")
    if not timedelta(0) < expires - created <= timedelta(seconds=MAX_APPROVAL_SECONDS):
        raise ValueError("Agent approval expiry must be within 24 hours")
    body = {
        "schema_version": APPROVAL_REQUEST_VERSION,
        "status": "pending",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "registry_binding_sha256": checkpoint["registry_binding_sha256"],
        "requested_by": "workbench-control-plane",
        "requested_action": action,
        "reason": reason.strip(),
        "evidence_ids": copy.deepcopy(evidence_ids),
        "created_at": _timestamp(created_at, "created_at"),
        "expires_at": _timestamp(expires_at, "expires_at"),
        "execution_authorized": False,
        "boundary": APPROVAL_BOUNDARY,
    }
    return {"request_id": digest(body), **body}


def verify_agent_approval_request(
    checkpoint: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    verify_agent_checkpoint(checkpoint)
    fields = {
        "request_id",
        "schema_version",
        "status",
        "checkpoint_id",
        "registry_binding_sha256",
        "requested_by",
        "requested_action",
        "reason",
        "evidence_ids",
        "created_at",
        "expires_at",
        "execution_authorized",
        "boundary",
    }
    if (
        not isinstance(request, dict)
        or set(request) != fields
        or request.get("schema_version") != APPROVAL_REQUEST_VERSION
        or request.get("status") != "pending"
        or request.get("checkpoint_id") != checkpoint["checkpoint_id"]
        or request.get("registry_binding_sha256")
        != checkpoint["registry_binding_sha256"]
        or request.get("requested_by") != "workbench-control-plane"
        or request.get("execution_authorized") is not False
        or request.get("boundary") != APPROVAL_BOUNDARY
        or not isinstance(request.get("reason"), str)
        or not 0 < len(request["reason"]) <= 1000
        or request["reason"] != request["reason"].strip()
        or not isinstance(request.get("evidence_ids"), list)
        or not request["evidence_ids"]
        or len(request["evidence_ids"]) != len(set(request["evidence_ids"]))
        or not set(request["evidence_ids"]) <= _observations(checkpoint)
    ):
        raise ValueError("Invalid Agent approval request")
    _validate_action(request["requested_action"])
    if request["requested_action"]["tool_name"] in {
        tool["name"] for tool in checkpoint["tool_manifest"]
    }:
        raise ValueError("Agent approval request targets a registered read tool")
    created = _parse_timestamp(request["created_at"], "created_at")
    expires = _parse_timestamp(request["expires_at"], "expires_at")
    if not timedelta(0) < expires - created <= timedelta(seconds=MAX_APPROVAL_SECONDS):
        raise ValueError("Invalid Agent approval expiry")
    if request["request_id"] != digest(
        {key: request[key] for key in request if key != "request_id"}
    ):
        raise ValueError("Agent approval request ID does not bind request content")
    return {
        "status": "passed",
        "request_id": request["request_id"],
        "approval_state": "pending",
        "execution_authorized": False,
    }


def build_agent_approval_decision(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    *,
    status: str,
    decided_at: datetime,
    actor_id: str | None = None,
    reason: str,
) -> dict[str, Any]:
    """Transition a pending request once; every terminal state remains non-executing."""
    verify_agent_approval_request(checkpoint, request)
    if status not in APPROVAL_STATES:
        raise ValueError("Invalid Agent approval decision state")
    decided_text = _timestamp(decided_at, "decided_at")
    decided = _parse_timestamp(decided_text, "decided_at")
    created = _parse_timestamp(request["created_at"], "created_at")
    expires = _parse_timestamp(request["expires_at"], "expires_at")
    if decided < created:
        raise ValueError("Agent approval decision precedes its request")
    if status == "expired":
        if decided < expires or actor_id is not None or reason != "request_expired":
            raise ValueError("Invalid Agent approval expiry transition")
        actor = {"kind": "system", "id": "workbench-expiry"}
    else:
        if decided >= expires:
            raise ValueError("Agent approval request has expired")
        if (
            not isinstance(actor_id, str)
            or not 0 < len(actor_id.strip()) <= 200
            or not isinstance(reason, str)
            or not 0 < len(reason.strip()) <= 1000
        ):
            raise ValueError("Invalid Agent approval operator decision")
        actor = {"kind": "operator", "id": actor_id.strip()}
        reason = reason.strip()
    body = {
        "schema_version": APPROVAL_DECISION_VERSION,
        "status": status,
        "request_id": request["request_id"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "action_call_id": request["requested_action"]["call_id"],
        "decided_at": decided_text,
        "actor": actor,
        "reason": reason,
        "execution_authorized": False,
        "boundary": APPROVAL_BOUNDARY,
    }
    return {"decision_id": digest(body), **body}


def verify_agent_approval_decision(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    verify_agent_approval_request(checkpoint, request)
    fields = {
        "decision_id",
        "schema_version",
        "status",
        "request_id",
        "checkpoint_id",
        "action_call_id",
        "decided_at",
        "actor",
        "reason",
        "execution_authorized",
        "boundary",
    }
    if (
        not isinstance(decision, dict)
        or set(decision) != fields
        or decision.get("schema_version") != APPROVAL_DECISION_VERSION
        or decision.get("status") not in APPROVAL_STATES
        or decision.get("request_id") != request["request_id"]
        or decision.get("checkpoint_id") != checkpoint["checkpoint_id"]
        or decision.get("action_call_id")
        != request["requested_action"]["call_id"]
        or decision.get("execution_authorized") is not False
        or decision.get("boundary") != APPROVAL_BOUNDARY
    ):
        raise ValueError("Invalid Agent approval decision")
    reason = decision.get("reason")
    if not isinstance(reason, str):
        raise ValueError("Agent approval decision reason must be a string")
    expected = build_agent_approval_decision(
        checkpoint,
        request,
        status=decision["status"],
        decided_at=_parse_timestamp(decision["decided_at"], "decided_at"),
        actor_id=(
            decision["actor"].get("id")
            if isinstance(decision.get("actor"), dict)
            and decision["actor"].get("kind") == "operator"
            else None
        ),
        reason=reason,
    )
    if decision != expected:
        raise ValueError("Agent approval decision differs from request-bound state")
    return {
        "status": "passed",
        "request_id": request["request_id"],
        "decision_id": decision["decision_id"],
        "approval_state": decision["status"],
        "execution_authorized": False,
    }


def save_agent_approval_request(
    checkpoint: dict[str, Any], request: dict[str, Any], output: Path
) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Agent approval request output must be absent")
    verify_agent_approval_request(checkpoint, request)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(request) + "\n", encoding="utf-8", newline="\n")
    return request


def save_agent_approval_decision(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Agent approval decision output must be absent")
    verify_agent_approval_decision(checkpoint, request, decision)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(decision) + "\n", encoding="utf-8", newline="\n")
    return decision


def load_and_verify_agent_approval(
    checkpoint_path: Path,
    request_path: Path,
    decision_path: Path | None = None,
) -> dict[str, Any]:
    checkpoint = read(checkpoint_path)
    request = read(request_path)
    if decision_path is None:
        return verify_agent_approval_request(checkpoint, request)
    return verify_agent_approval_decision(checkpoint, request, read(decision_path))
