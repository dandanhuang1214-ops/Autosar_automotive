"""Local one-shot approval claim and non-executing transaction receipts.

The ledger rehearses concurrency and crash recovery without registering or running a
side-effect tool. It is a local filesystem coordination domain, not a distributed
authorization service or an authenticated operator identity.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.agent_approval import verify_agent_approval_decision
from automotive_workbench.agent_runtime import verify_agent_checkpoint
from automotive_workbench.project_explanation import canonical, digest, read


APPROVAL_CLAIM_VERSION = "readonly-agent-approval-claim-0.1"
TRANSACTION_RECEIPT_VERSION = "readonly-agent-transaction-receipt-0.1"
TRANSACTION_BOUNDARY = (
    "This local transaction consumes one approval decision for a non-executing "
    "rehearsal. It does not authenticate an operator or authorize or perform a "
    "side effect."
)
RECEIPT_STATES = {"simulated", "aborted"}


def _timestamp(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"Agent transaction {name} requires a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Invalid Agent transaction {name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid Agent transaction {name}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Agent transaction {name} requires a timezone")
    return parsed.astimezone(timezone.utc)


def _transaction_id(
    checkpoint: dict[str, Any], request: dict[str, Any]
) -> str:
    return digest(
        {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "request_id": request["request_id"],
            "action_call_id": request["requested_action"]["call_id"],
        }
    )


def transaction_paths(
    ledger: Path, checkpoint: dict[str, Any], request: dict[str, Any]
) -> tuple[Path, Path]:
    transaction = ledger / _transaction_id(checkpoint, request)
    return transaction / "claim.json", transaction / "receipt.json"


def build_agent_approval_claim(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    *,
    claimed_at: datetime,
) -> dict[str, Any]:
    verified = verify_agent_approval_decision(checkpoint, request, decision)
    if verified["approval_state"] != "approved":
        raise ValueError("Only an approved Agent request can be claimed")
    claimed_text = _timestamp(claimed_at, "claimed_at")
    claimed = _parse_timestamp(claimed_text, "claimed_at")
    decided = _parse_timestamp(decision["decided_at"], "decided_at")
    expires = _parse_timestamp(request["expires_at"], "expires_at")
    if claimed < decided:
        raise ValueError("Agent approval claim precedes its decision")
    if claimed >= expires:
        raise ValueError("Agent approval claim is stale")
    body = {
        "schema_version": APPROVAL_CLAIM_VERSION,
        "status": "claimed",
        "transaction_id": _transaction_id(checkpoint, request),
        "request_id": request["request_id"],
        "decision_id": decision["decision_id"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "action_call_id": request["requested_action"]["call_id"],
        "claimed_at": claimed_text,
        "execution_authorized": False,
        "side_effect_performed": False,
        "boundary": TRANSACTION_BOUNDARY,
    }
    return {"claim_id": digest(body), **body}


def verify_agent_approval_claim(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    claim: dict[str, Any],
) -> dict[str, Any]:
    verify_agent_checkpoint(checkpoint)
    fields = {
        "claim_id",
        "schema_version",
        "status",
        "transaction_id",
        "request_id",
        "decision_id",
        "checkpoint_id",
        "action_call_id",
        "claimed_at",
        "execution_authorized",
        "side_effect_performed",
        "boundary",
    }
    if (
        not isinstance(claim, dict)
        or set(claim) != fields
        or claim.get("schema_version") != APPROVAL_CLAIM_VERSION
        or claim.get("status") != "claimed"
        or claim.get("execution_authorized") is not False
        or claim.get("side_effect_performed") is not False
        or claim.get("boundary") != TRANSACTION_BOUNDARY
    ):
        raise ValueError("Invalid Agent approval claim")
    expected = build_agent_approval_claim(
        checkpoint,
        request,
        decision,
        claimed_at=_parse_timestamp(claim["claimed_at"], "claimed_at"),
    )
    if claim != expected:
        raise ValueError("Agent approval claim differs from its bound decision")
    return {
        "status": "passed",
        "transaction_id": claim["transaction_id"],
        "claim_id": claim["claim_id"],
        "transaction_state": "claimed",
        "execution_authorized": False,
        "side_effect_performed": False,
    }


def build_agent_transaction_receipt(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    claim: dict[str, Any],
    *,
    status: str,
    reason: str,
    completed_at: datetime,
) -> dict[str, Any]:
    verify_agent_approval_claim(checkpoint, request, decision, claim)
    if status not in RECEIPT_STATES:
        raise ValueError("Invalid Agent transaction receipt state")
    if not isinstance(reason, str) or not 0 < len(reason.strip()) <= 1000:
        raise ValueError("Invalid Agent transaction receipt reason")
    completed_text = _timestamp(completed_at, "completed_at")
    if _parse_timestamp(completed_text, "completed_at") < _parse_timestamp(
        claim["claimed_at"], "claimed_at"
    ):
        raise ValueError("Agent transaction receipt precedes its claim")
    body = {
        "schema_version": TRANSACTION_RECEIPT_VERSION,
        "status": status,
        "transaction_id": claim["transaction_id"],
        "claim_id": claim["claim_id"],
        "request_id": request["request_id"],
        "decision_id": decision["decision_id"],
        "completed_at": completed_text,
        "reason": reason.strip(),
        "execution_authorized": False,
        "side_effect_performed": False,
        "boundary": TRANSACTION_BOUNDARY,
    }
    return {"receipt_id": digest(body), **body}


def verify_agent_transaction_receipt(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    claim: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "receipt_id",
        "schema_version",
        "status",
        "transaction_id",
        "claim_id",
        "request_id",
        "decision_id",
        "completed_at",
        "reason",
        "execution_authorized",
        "side_effect_performed",
        "boundary",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != fields
        or receipt.get("schema_version") != TRANSACTION_RECEIPT_VERSION
        or receipt.get("status") not in RECEIPT_STATES
        or not isinstance(receipt.get("reason"), str)
        or receipt.get("execution_authorized") is not False
        or receipt.get("side_effect_performed") is not False
        or receipt.get("boundary") != TRANSACTION_BOUNDARY
    ):
        raise ValueError("Invalid Agent transaction receipt")
    expected = build_agent_transaction_receipt(
        checkpoint,
        request,
        decision,
        claim,
        status=receipt["status"],
        reason=receipt["reason"],
        completed_at=_parse_timestamp(receipt["completed_at"], "completed_at"),
    )
    if receipt != expected:
        raise ValueError("Agent transaction receipt differs from its claim")
    return {
        "status": "passed",
        "transaction_id": claim["transaction_id"],
        "claim_id": claim["claim_id"],
        "receipt_id": receipt["receipt_id"],
        "transaction_state": receipt["status"],
        "execution_authorized": False,
        "side_effect_performed": False,
    }


def _prepare_paths(
    ledger: Path, checkpoint: dict[str, Any], request: dict[str, Any]
) -> tuple[Path, Path]:
    if ledger.is_symlink():
        raise ValueError("Agent transaction ledger must not be a symlink")
    ledger.mkdir(parents=True, exist_ok=True)
    if not ledger.is_dir():
        raise ValueError("Agent transaction ledger must be a directory")
    claim_path, receipt_path = transaction_paths(ledger, checkpoint, request)
    transaction = claim_path.parent
    if transaction.is_symlink():
        raise ValueError("Agent transaction directory must not be a symlink")
    transaction.mkdir(exist_ok=True)
    if not transaction.is_dir():
        raise ValueError("Agent transaction path must be a directory")
    return claim_path, receipt_path


def _write_exclusive(path: Path, artifact: dict[str, Any]) -> None:
    data = (canonical(artifact) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def claim_agent_approval(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    ledger: Path,
    *,
    claimed_at: datetime,
) -> dict[str, Any]:
    claim = build_agent_approval_claim(
        checkpoint, request, decision, claimed_at=claimed_at
    )
    claim_path, _ = _prepare_paths(ledger, checkpoint, request)
    try:
        _write_exclusive(claim_path, claim)
    except FileExistsError:
        existing = read(claim_path)
        verify_agent_approval_claim(checkpoint, request, decision, existing)
        return existing
    return claim


def complete_agent_transaction(
    checkpoint: dict[str, Any],
    request: dict[str, Any],
    decision: dict[str, Any],
    ledger: Path,
    *,
    status: str,
    reason: str,
    completed_at: datetime,
) -> dict[str, Any]:
    claim_path, receipt_path = _prepare_paths(ledger, checkpoint, request)
    if not claim_path.exists() or claim_path.is_symlink():
        raise ValueError("Agent approval must be claimed before completion")
    claim = read(claim_path)
    verify_agent_approval_claim(checkpoint, request, decision, claim)
    receipt = build_agent_transaction_receipt(
        checkpoint,
        request,
        decision,
        claim,
        status=status,
        reason=reason,
        completed_at=completed_at,
    )
    try:
        _write_exclusive(receipt_path, receipt)
    except FileExistsError:
        existing = read(receipt_path)
        verify_agent_transaction_receipt(
            checkpoint, request, decision, claim, existing
        )
        if existing["status"] != status or existing["reason"] != reason.strip():
            raise ValueError("Agent transaction already has another terminal receipt")
        return existing
    return receipt


def load_and_verify_agent_transaction(
    checkpoint_path: Path,
    request_path: Path,
    decision_path: Path,
    ledger: Path,
) -> dict[str, Any]:
    checkpoint = read(checkpoint_path)
    request = read(request_path)
    decision = read(decision_path)
    claim_path, receipt_path = transaction_paths(ledger, checkpoint, request)
    if ledger.is_symlink() or not ledger.is_dir():
        raise ValueError("Agent transaction ledger is missing or unsafe")
    if claim_path.parent.is_symlink() or not claim_path.parent.is_dir():
        raise ValueError("Agent transaction directory is missing or unsafe")
    if claim_path.is_symlink() or not claim_path.exists():
        raise ValueError("Agent transaction claim is missing")
    claim = read(claim_path)
    verified = verify_agent_approval_claim(
        checkpoint, request, decision, claim
    )
    if receipt_path.exists():
        if receipt_path.is_symlink():
            raise ValueError("Agent transaction receipt must not be a symlink")
        receipt = read(receipt_path)
        if receipt.get("schema_version") == "agent-virtual-execution-receipt-0.1":
            from automotive_workbench.agent_virtual_execution import (
                verify_virtual_execution_receipt,
                virtual_execution_paths,
            )

            attempt_path, _ = virtual_execution_paths(
                ledger, checkpoint, request
            )
            if attempt_path.is_symlink() or not attempt_path.is_file():
                raise ValueError("Agent virtual execution attempt is missing or unsafe")
            return verify_virtual_execution_receipt(
                request, claim, read(attempt_path), receipt
            )
        return verify_agent_transaction_receipt(
            checkpoint, request, decision, claim, receipt
        )
    return verified
