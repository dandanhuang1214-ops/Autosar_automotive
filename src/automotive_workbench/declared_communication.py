"""Execute preflighted classic-CAN vectors on two local backend endpoints."""

from __future__ import annotations

import html
import json
import math
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.can_backend import probe_can_backend
from automotive_workbench.can_io import (
    BusConfig,
    bus_isolation_evidence,
    open_bus,
    sha256_file,
)
from automotive_workbench.can_runtime import _python_can
from automotive_workbench.communication_plan import preflight_communication


def vector_filter(vector: dict[str, Any]) -> dict[str, Any]:
    return {
        "can_id": vector["frame_id"],
        "can_mask": 0x1FFFFFFF if vector["is_extended_id"] else 0x7FF,
        "extended": vector["is_extended_id"],
    }


def _empty_result(vector: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "id": vector["id"],
        "message": vector["message"],
        "direction": vector["direction"],
        "sender": "local" if vector["direction"] == "tx" else "peer",
        "receiver": "peer" if vector["direction"] == "tx" else "local",
        "status": status,
        "reason": reason,
        "observed": None,
        "error": None,
        "cleanup": [],
    }


def _error(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def exchange_vector(
    database: Any, vector: dict[str, Any], config: BusConfig
) -> dict[str, Any]:
    """Use fresh filtered endpoints per vector so prior frames cannot satisfy it.

    This is an in-process peer exchange, not a physical ECU responder. Each opened
    endpoint is closed independently even if another endpoint's cleanup fails.
    """
    result = _empty_result(vector, "failed", "runtime_error")
    endpoints: list[tuple[str, Any]] = []
    try:
        can = _python_can()
        filters = [vector_filter(vector)]
        local = open_bus(config, filters)
        endpoints.append(("local", local))
        peer = open_bus(config, filters)
        endpoints.append(("peer", peer))
        sender, receiver = (
            (local, peer) if vector["direction"] == "tx" else (peer, local)
        )
        message = can.Message(
            arbitration_id=vector["frame_id"],
            is_extended_id=vector["is_extended_id"],
            data=bytes.fromhex(vector["payload_hex"]),
            check=True,
        )
        deadline = time.monotonic() + vector["timeout_seconds"]
        sender.send(message, timeout=vector["timeout_seconds"])
        remaining = deadline - time.monotonic()
        frame = receiver.recv(timeout=max(0.0, remaining)) if remaining > 0 else None
        if frame is None:
            result["reason"] = "receive_timeout"
        else:
            observed = {
                "frame_id": frame.arbitration_id,
                "is_extended_id": frame.is_extended_id,
                "is_fd": frame.is_fd,
                "is_remote_frame": frame.is_remote_frame,
                "is_error_frame": frame.is_error_frame,
                "dlc": frame.dlc,
                "payload_hex": bytes(frame.data).hex(),
                "raw_signals": None,
                "signals": None,
            }
            result["observed"] = observed
            if (
                frame.arbitration_id != vector["frame_id"]
                or frame.is_extended_id != vector["is_extended_id"]
            ):
                result["reason"] = "frame_identity_mismatch"
            elif frame.is_fd or frame.is_remote_frame or frame.is_error_frame:
                result["reason"] = "unsupported_frame"
            elif frame.dlc != vector["dlc"] or len(frame.data) != vector["dlc"]:
                result["reason"] = "frame_length_mismatch"
            else:
                definition = database.get_message_by_name(vector["message"])
                observed["raw_signals"] = definition.decode(
                    frame.data, scaling=False, decode_choices=False
                )
                decoded = definition.decode(frame.data, decode_choices=False)
                if not all(math.isfinite(value) for value in decoded.values()):
                    raise ValueError("Received signals decode to non-finite values")
                observed["signals"] = decoded
                if observed["raw_signals"] != vector["expected_raw_signals"]:
                    result["reason"] = "signal_mismatch"
                else:
                    result["status"] = "passed"
                    result["reason"] = ""
    except Exception as exc:
        result["reason"] = "runtime_error"
        result["error"] = _error(exc)
    finally:
        for role, bus in reversed(endpoints):
            cleanup: dict[str, Any] = {
                "endpoint": role,
                "status": "passed",
                "error": None,
            }
            try:
                bus.shutdown()
            except Exception as exc:
                cleanup["status"] = "failed"
                cleanup["error"] = _error(exc)
                if result["status"] == "passed":
                    result["reason"] = "cleanup_failed"
                result["status"] = "failed"
            result["cleanup"].append(cleanup)
    return result


def run_declared_communication(
    dbc: Path,
    intent: Path,
    declaration: Path,
    config: BusConfig,
    output: Path,
) -> dict[str, Any]:
    # Every input/config/output rejection precedes probe (which itself opens a bus).
    if config.interface not in {"virtual", "socketcan"}:
        raise ValueError("Declared communication supports virtual or socketcan")
    if not isinstance(config.channel, str) or not config.channel.strip():
        raise ValueError("A non-empty channel is required")
    if config.fd is not False or config.receive_own_messages is not False:
        raise ValueError(
            "Declared communication requires classic CAN without self reception"
        )
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Runtime output must be empty or absent")
    initial_hashes = [sha256_file(path) for path in (dbc, intent, declaration)]
    plan = preflight_communication(dbc, intent, declaration)
    database = _load_dbc(dbc)
    if initial_hashes != [
        item["sha256"] for item in plan["source_artifacts"]
    ] or initial_hashes != [sha256_file(path) for path in (dbc, intent, declaration)]:
        raise ValueError("Communication inputs changed during preflight")
    filters = []
    for vector in plan["vectors"]:
        item = vector_filter(vector)
        if item not in filters:
            filters.append(item)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    try:
        probe = probe_can_backend(config)
    except Exception as exc:
        probe = {
            "artifact_type": "can-backend-capability",
            "status": "failed",
            "reason": "probe_runtime_error",
            "error": _error(exc),
        }
    vectors = {}
    for vector in plan["vectors"]:
        vectors[vector["id"]] = (
            _empty_result(vector, "blocked", probe["reason"])
            if probe["status"] != "available"
            else exchange_vector(database, vector, config)
        )
    status = (
        probe["status"]
        if probe["status"] != "available"
        else (
            "passed"
            if all(item["status"] == "passed" for item in vectors.values())
            else "failed"
        )
    )
    report = {
        "artifact_type": "declared-communication-runtime",
        "schema_version": "declared-communication-runtime-0.1",
        "started_at": started_at,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "bus_config": asdict(config),
        "backend_probe": probe,
        "isolation": {
            **bus_isolation_evidence(config, filters),
            "endpoint_lifetime": "per_vector",
        },
        "source_artifacts": plan["source_artifacts"],
        "plan": plan,
        "status": status,
        "reason": probe["reason"]
        if probe["status"] != "available"
        else "vector_failed"
        if status == "failed"
        else "",
        "vector_count": len(vectors),
        "passed_count": sum(item["status"] == "passed" for item in vectors.values()),
        "vectors": vectors,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "declared-runtime-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Declared CAN Communication",
        "",
        f"Status: **{status}**",
        "",
        f"Backend: `{config.interface}`; channel: {html.escape(config.channel)}",
        "",
        "| Vector | Message | Direction | Status | Reason |",
        "|---|---|---|---|---|",
    ]
    for item in vectors.values():
        # DBC names are external text; prevent Markdown table/HTML injection.
        name = (
            html.escape(item["message"])
            .replace("|", "&#124;")
            .replace("\n", " ")
            .replace("\r", " ")
        )
        lines.append(
            f"| {item['id']} | {name} | {item['direction']} | {item['status']} | {item['reason']} |"
        )
    lines.extend(
        [
            "",
            "Two local backend endpoints exchange frames. No physical ECU, BSW stack, electrical bus or target timing is validated.",
            "",
        ]
    )
    (output / "declared-runtime-report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return report
