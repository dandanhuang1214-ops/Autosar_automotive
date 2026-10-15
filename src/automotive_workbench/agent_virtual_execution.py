"""Explicitly gated execution of one isolated virtual CAN action.

This module is intentionally separate from the model-facing read-only registry.  An
approval artifact records review but is not an authenticated authorization token;
the caller must also enable this local execution gate explicitly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.agent_transaction import (
    _prepare_paths,
    _parse_timestamp,
    _timestamp,
    _write_exclusive,
    transaction_paths,
    verify_agent_approval_claim,
)
from automotive_workbench.can_io import BusConfig, exact_can_filters, open_bus
from automotive_workbench.can_runtime import _python_can
from automotive_workbench.project_explanation import digest, read


VIRTUAL_CAN_TOOL = "virtual_can.send_once"
VIRTUAL_EXECUTION_ATTEMPT_VERSION = "agent-virtual-execution-attempt-0.1"
VIRTUAL_EXECUTION_RECEIPT_VERSION = "agent-virtual-execution-receipt-0.1"
VIRTUAL_EXECUTION_SCOPE = "isolated_process_local_virtual_can"
VIRTUAL_EXECUTION_BOUNDARY = (
    "This receipt records an explicitly enabled process-local virtual CAN action. "
    "The approval is not authenticated authorization, no hardware or configuration "
    "write is permitted, and uniqueness is limited to one local ledger."
)


def _virtual_channel(transaction_id: str) -> str:
    return f"workbench-agent-{transaction_id[:24]}"


def virtual_execution_paths(
    ledger: Path, checkpoint: dict[str, Any], request: dict[str, Any]
) -> tuple[Path, Path]:
    claim_path, receipt_path = transaction_paths(ledger, checkpoint, request)
    return claim_path.parent / "execution-attempt.json", receipt_path


def _validate_action(request: dict[str, Any]) -> dict[str, Any]:
    action = request.get("requested_action")
    if (
        not isinstance(action, dict)
        or action.get("tool_name") != VIRTUAL_CAN_TOOL
        or action.get("permission") != "execute"
    ):
        raise ValueError("Agent virtual execution requires the exact execute tool")
    arguments = action.get("arguments")
    if not isinstance(arguments, dict) or set(arguments) != {"frame_id", "payload_hex"}:
        raise ValueError("Invalid virtual CAN tool arguments")
    frame_id = arguments.get("frame_id")
    payload_hex = arguments.get("payload_hex")
    if (
        isinstance(frame_id, bool)
        or not isinstance(frame_id, int)
        or not 0 <= frame_id <= 0x7FF
        or not isinstance(payload_hex, str)
        or len(payload_hex) > 16
        or len(payload_hex) % 2
    ):
        raise ValueError("Invalid virtual CAN tool arguments")
    try:
        bytes.fromhex(payload_hex)
    except ValueError as exc:
        raise ValueError("Invalid virtual CAN tool arguments") from exc
    return arguments


def build_virtual_execution_attempt(
    request: dict[str, Any], claim: dict[str, Any], *, started_at: datetime
) -> dict[str, Any]:
    arguments = _validate_action(request)
    started_text = _timestamp(started_at, "started_at")
    if _parse_timestamp(started_text, "started_at") < _parse_timestamp(
        claim["claimed_at"], "claimed_at"
    ):
        raise ValueError("Agent virtual execution attempt precedes its claim")
    body = {
        "schema_version": VIRTUAL_EXECUTION_ATTEMPT_VERSION,
        "status": "started",
        "transaction_id": claim["transaction_id"],
        "claim_id": claim["claim_id"],
        "request_id": request["request_id"],
        "decision_id": claim["decision_id"],
        "action_call_id": claim["action_call_id"],
        "tool_name": VIRTUAL_CAN_TOOL,
        "arguments_sha256": digest(arguments),
        "idempotency_key": claim["transaction_id"],
        "started_at": started_text,
        "execution_scope": VIRTUAL_EXECUTION_SCOPE,
        "virtual_channel": _virtual_channel(claim["transaction_id"]),
        "local_execution_gate": "explicit_enable_flag",
        "hardware_accessed": False,
        "configuration_written": False,
        "authenticated_authorization": False,
        "boundary": VIRTUAL_EXECUTION_BOUNDARY,
    }
    return {"attempt_id": digest(body), **body}


def verify_virtual_execution_attempt(
    request: dict[str, Any], claim: dict[str, Any], attempt: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        "attempt_id", "schema_version", "status", "transaction_id", "claim_id",
        "request_id", "decision_id", "action_call_id", "tool_name",
        "arguments_sha256", "idempotency_key", "started_at", "execution_scope",
        "virtual_channel", "local_execution_gate",
        "hardware_accessed", "configuration_written", "authenticated_authorization",
        "boundary",
    }
    if (
        not isinstance(attempt, dict)
        or set(attempt) != fields
        or attempt.get("schema_version") != VIRTUAL_EXECUTION_ATTEMPT_VERSION
        or attempt.get("status") != "started"
        or attempt.get("execution_scope") != VIRTUAL_EXECUTION_SCOPE
        or attempt.get("virtual_channel") != _virtual_channel(claim["transaction_id"])
        or attempt.get("local_execution_gate") != "explicit_enable_flag"
        or attempt.get("hardware_accessed") is not False
        or attempt.get("configuration_written") is not False
        or attempt.get("authenticated_authorization") is not False
        or attempt.get("boundary") != VIRTUAL_EXECUTION_BOUNDARY
    ):
        raise ValueError("Invalid Agent virtual execution attempt")
    started = datetime.fromisoformat(str(attempt.get("started_at", "")).replace("Z", "+00:00"))
    expected = build_virtual_execution_attempt(request, claim, started_at=started)
    if attempt != expected:
        raise ValueError("Agent virtual execution attempt differs from its claim")
    return attempt


def _frame_record(frame_id: int, payload: bytes) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "frame_id_hex": f"0x{frame_id:03X}",
        "payload_hex": payload.hex().upper(),
    }


def _valid_frame_record(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "frame_id", "frame_id_hex", "payload_hex"
    }:
        return False
    frame_id = value.get("frame_id")
    payload_hex = value.get("payload_hex")
    return (
        isinstance(frame_id, int)
        and not isinstance(frame_id, bool)
        and 0 <= frame_id <= 0x7FF
        and value.get("frame_id_hex") == f"0x{frame_id:03X}"
        and isinstance(payload_hex, str)
        and payload_hex == payload_hex.upper()
        and len(payload_hex) <= 16
        and len(payload_hex) % 2 == 0
        and all(character in "0123456789ABCDEF" for character in payload_hex)
    )


def _run_virtual_can_action(
    transaction_id: str, arguments: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    frame_id = arguments["frame_id"]
    payload = bytes.fromhex(arguments["payload_hex"])
    channel = _virtual_channel(transaction_id)
    config = BusConfig("virtual", channel)
    sender = None
    receiver = None
    command: dict[str, Any] = {"status": "not_run", "send_invoked": False, "error_type": None}
    effect: dict[str, Any] = {
        "status": "not_run",
        "expected_frame": _frame_record(frame_id, payload),
        "observed_frame": None,
        "error_type": None,
    }
    cleanup_errors: list[str] = []
    side_effect_status = "not_performed"
    try:
        receiver = open_bus(config, exact_can_filters(frame_id))
        sender = open_bus(config)
        message = _python_can().Message(
            arbitration_id=frame_id,
            data=payload,
            is_extended_id=False,
        )
    except Exception as exc:
        command["status"] = "raised"
        command["error_type"] = type(exc).__name__
    else:
        try:
            command["send_invoked"] = True
            side_effect_status = "indeterminate"
            sender.send(message, timeout=0.2)
        except Exception as exc:
            command["status"] = "raised"
            command["error_type"] = type(exc).__name__
        else:
            side_effect_status = "performed"
            command["status"] = "returned"
            try:
                observed = receiver.recv(timeout=0.25)
            except Exception as exc:
                effect["status"] = "failed"
                effect["error_type"] = type(exc).__name__
            else:
                if observed is not None:
                    effect["observed_frame"] = _frame_record(
                        observed.arbitration_id, bytes(observed.data)
                    )
                effect["status"] = (
                    "passed"
                    if effect["observed_frame"] == effect["expected_frame"]
                    else "failed"
                )
    finally:
        for name, bus in (("sender", sender), ("receiver", receiver)):
            if bus is not None:
                try:
                    bus.shutdown()
                except Exception as exc:  # pragma: no cover - backend defensive path
                    cleanup_errors.append(f"{name}:{type(exc).__name__}")

    residual = None
    try:
        observer = open_bus(config, exact_can_filters(frame_id))
        try:
            residual_message = observer.recv(timeout=0.03)
            residual = None if residual_message is None else _frame_record(
                residual_message.arbitration_id, bytes(residual_message.data)
            )
        finally:
            observer.shutdown()
    except Exception as exc:  # pragma: no cover - backend defensive path
        cleanup_errors.append(f"observer:{type(exc).__name__}")
    compensation = {
        "status": "passed" if not cleanup_errors and residual is None else "failed",
        "mechanism": "shutdown_owned_bus_handles_and_probe_no_buffered_frame",
        "literal_undo": False,
        "residual_observation": residual,
        "errors": cleanup_errors,
    }
    return command, effect, compensation, side_effect_status


def _validate_execution_results(
    request: dict[str, Any],
    command: Any,
    effect: Any,
    compensation: Any,
    side_effect_status: Any,
) -> None:
    if (
        not isinstance(command, dict)
        or set(command) != {"status", "send_invoked", "error_type"}
        or command.get("status") not in {"not_run", "returned", "raised"}
        or not isinstance(command.get("send_invoked"), bool)
        or not (
            command.get("error_type") is None
            or isinstance(command.get("error_type"), str)
        )
        or (
            command.get("status") == "returned"
            and (
                command.get("send_invoked") is not True
                or command.get("error_type") is not None
            )
        )
        or (
            command.get("status") == "raised"
            and not command.get("error_type")
        )
        or (
            command.get("status") == "not_run"
            and (
                command.get("send_invoked") is not False
                or command.get("error_type") is not None
            )
        )
    ):
        raise ValueError("Invalid Agent virtual execution command result")
    arguments = _validate_action(request)
    expected = _frame_record(
        arguments["frame_id"], bytes.fromhex(arguments["payload_hex"])
    )
    if (
        not isinstance(effect, dict)
        or set(effect)
        != {"status", "expected_frame", "observed_frame", "error_type"}
        or effect.get("status") not in {"not_run", "passed", "failed"}
        or not (
            effect.get("error_type") is None
            or isinstance(effect.get("error_type"), str)
        )
        or effect.get("expected_frame") != expected
        or not (
            effect.get("observed_frame") is None
            or _valid_frame_record(effect.get("observed_frame"))
        )
        or (effect.get("status") == "passed" and effect.get("observed_frame") != expected)
        or (effect.get("status") == "passed" and effect.get("error_type") is not None)
        or (
            effect.get("status") == "not_run"
            and (
                effect.get("observed_frame") is not None
                or effect.get("error_type") is not None
            )
        )
    ):
        raise ValueError("Invalid Agent virtual execution effect verification")
    if (
        not isinstance(compensation, dict)
        or set(compensation)
        != {"status", "mechanism", "literal_undo", "residual_observation", "errors"}
        or compensation.get("status") not in {"passed", "failed"}
        or compensation.get("mechanism")
        != "shutdown_owned_bus_handles_and_probe_no_buffered_frame"
        or compensation.get("literal_undo") is not False
        or not isinstance(compensation.get("errors"), list)
        or any(not isinstance(item, str) for item in compensation["errors"])
        or not (
            compensation.get("residual_observation") is None
            or _valid_frame_record(compensation.get("residual_observation"))
        )
        or (
            compensation.get("status") == "passed"
            and (compensation.get("residual_observation") is not None or compensation["errors"])
        )
        or side_effect_status not in {"not_performed", "performed", "indeterminate"}
        or (command.get("status") == "returned" and side_effect_status != "performed")
        or (command.get("status") == "raised" and command.get("send_invoked") and side_effect_status != "indeterminate")
        or (command.get("status") == "raised" and not command.get("send_invoked") and side_effect_status != "not_performed")
        or (command.get("status") == "not_run" and side_effect_status != "not_performed")
    ):
        raise ValueError("Invalid Agent virtual execution compensation")


def build_virtual_execution_receipt(
    request: dict[str, Any],
    claim: dict[str, Any],
    attempt: dict[str, Any],
    *,
    completed_at: datetime,
    command_result: dict[str, Any],
    effect_verification: dict[str, Any],
    compensation: dict[str, Any],
    side_effect_status: str,
) -> dict[str, Any]:
    verify_virtual_execution_attempt(request, claim, attempt)
    _validate_execution_results(
        request, command_result, effect_verification, compensation, side_effect_status
    )
    completed_text = _timestamp(completed_at, "completed_at")
    if _parse_timestamp(completed_text, "completed_at") < _parse_timestamp(
        attempt["started_at"], "started_at"
    ):
        raise ValueError("Agent virtual execution receipt precedes its attempt")
    status = (
        "succeeded"
        if command_result.get("status") == "returned"
        and effect_verification.get("status") == "passed"
        and compensation.get("status") == "passed"
        and side_effect_status == "performed"
        else "failed"
    )
    body = {
        "schema_version": VIRTUAL_EXECUTION_RECEIPT_VERSION,
        "status": status,
        "transaction_id": claim["transaction_id"],
        "claim_id": claim["claim_id"],
        "request_id": request["request_id"],
        "decision_id": claim["decision_id"],
        "attempt_id": attempt["attempt_id"],
        "tool_name": VIRTUAL_CAN_TOOL,
        "idempotency_key": claim["transaction_id"],
        "virtual_channel": _virtual_channel(claim["transaction_id"]),
        "completed_at": completed_text,
        "command_result": command_result,
        "effect_verification": effect_verification,
        "compensation": compensation,
        "side_effect_status": side_effect_status,
        "hardware_accessed": False,
        "configuration_written": False,
        "authenticated_authorization": False,
        "boundary": VIRTUAL_EXECUTION_BOUNDARY,
    }
    return {"receipt_id": digest(body), **body}


def verify_virtual_execution_receipt(
    request: dict[str, Any],
    claim: dict[str, Any],
    attempt: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "receipt_id", "schema_version", "status", "transaction_id", "claim_id",
        "request_id", "decision_id", "attempt_id", "tool_name", "idempotency_key",
        "virtual_channel",
        "completed_at", "command_result", "effect_verification", "compensation",
        "side_effect_status", "hardware_accessed", "configuration_written",
        "authenticated_authorization", "boundary",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != fields
        or receipt.get("schema_version") != VIRTUAL_EXECUTION_RECEIPT_VERSION
        or receipt.get("status") not in {"succeeded", "failed"}
        or receipt.get("virtual_channel") != _virtual_channel(claim["transaction_id"])
        or receipt.get("side_effect_status")
        not in {"not_performed", "performed", "indeterminate"}
        or receipt.get("hardware_accessed") is not False
        or receipt.get("configuration_written") is not False
        or receipt.get("authenticated_authorization") is not False
        or receipt.get("boundary") != VIRTUAL_EXECUTION_BOUNDARY
    ):
        raise ValueError("Invalid Agent virtual execution receipt")
    completed = datetime.fromisoformat(str(receipt.get("completed_at", "")).replace("Z", "+00:00"))
    expected = build_virtual_execution_receipt(
        request,
        claim,
        attempt,
        completed_at=completed,
        command_result=receipt["command_result"],
        effect_verification=receipt["effect_verification"],
        compensation=receipt["compensation"],
        side_effect_status=receipt["side_effect_status"],
    )
    if receipt != expected:
        raise ValueError("Agent virtual execution receipt differs from its attempt")
    return {
        "status": "passed",
        "transaction_id": claim["transaction_id"],
        "attempt_id": attempt["attempt_id"],
        "receipt_id": receipt["receipt_id"],
        "transaction_state": receipt["status"],
        "effect_status": receipt["effect_verification"]["status"],
        "compensation_status": receipt["compensation"]["status"],
        "hardware_accessed": False,
        "configuration_written": False,
        "authenticated_authorization": False,
    }


def execute_agent_virtual_can(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    ledger: Path,
    *,
    enabled: bool,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    if enabled is not True:
        raise ValueError("Agent virtual execution is disabled; explicit enable is required")
    _validate_action(request)
    claim_path, receipt_path = _prepare_paths(ledger, checkpoint, request)
    if claim_path.is_symlink() or not claim_path.exists():
        raise ValueError("Agent approval must be claimed before virtual execution")
    claim = read(claim_path)
    verify_agent_approval_claim(checkpoint, request, decision, claim)
    attempt_path, _ = virtual_execution_paths(ledger, checkpoint, request)
    if receipt_path.exists():
        if attempt_path.is_symlink() or receipt_path.is_symlink():
            raise ValueError("Agent virtual execution artifacts must not be symlinks")
        attempt = read(attempt_path)
        receipt = read(receipt_path)
        verify_virtual_execution_receipt(request, claim, attempt, receipt)
        return receipt

    attempt = build_virtual_execution_attempt(request, claim, started_at=started_at)
    try:
        _write_exclusive(attempt_path, attempt)
    except FileExistsError:
        if attempt_path.is_symlink():
            raise ValueError("Agent virtual execution attempt must not be a symlink")
        existing = read(attempt_path)
        verify_virtual_execution_attempt(request, claim, existing)
        if receipt_path.exists():
            if receipt_path.is_symlink():
                raise ValueError("Agent virtual execution receipt must not be a symlink")
            receipt = read(receipt_path)
            verify_virtual_execution_receipt(request, claim, existing, receipt)
            return receipt
        raise ValueError(
            "Agent virtual execution outcome is indeterminate; automatic retry blocked"
        )

    command, effect, compensation, side_effect_status = _run_virtual_can_action(
        claim["transaction_id"], request["requested_action"]["arguments"]
    )
    receipt = build_virtual_execution_receipt(
        request,
        claim,
        attempt,
        completed_at=completed_at or datetime.now(timezone.utc),
        command_result=command,
        effect_verification=effect,
        compensation=compensation,
        side_effect_status=side_effect_status,
    )
    try:
        _write_exclusive(receipt_path, receipt)
    except FileExistsError:
        if receipt_path.is_symlink():
            raise ValueError("Agent virtual execution receipt must not be a symlink")
        existing = read(receipt_path)
        verify_virtual_execution_receipt(request, claim, attempt, existing)
        return existing
    return receipt


def load_and_verify_virtual_execution(
    checkpoint_path: Path,
    request_path: Path,
    decision_path: Path,
    ledger: Path,
) -> dict[str, Any]:
    checkpoint = read(checkpoint_path)
    request = read(request_path)
    decision = read(decision_path)
    claim_path, receipt_path = transaction_paths(ledger, checkpoint, request)
    attempt_path, _ = virtual_execution_paths(ledger, checkpoint, request)
    if any(path.is_symlink() for path in (ledger, claim_path.parent, claim_path, attempt_path, receipt_path)):
        raise ValueError("Agent virtual execution path must not be a symlink")
    if not all(path.is_file() for path in (claim_path, attempt_path, receipt_path)):
        raise ValueError("Agent virtual execution artifacts are incomplete")
    claim = read(claim_path)
    verify_agent_approval_claim(checkpoint, request, decision, claim)
    attempt = read(attempt_path)
    receipt = read(receipt_path)
    return verify_virtual_execution_receipt(request, claim, attempt, receipt)
