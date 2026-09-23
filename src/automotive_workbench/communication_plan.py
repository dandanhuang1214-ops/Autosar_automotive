"""Compile bounded numeric classic-CAN vectors without opening a bus or writing files."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc, validate_dbc_intent
from automotive_workbench.bsw_intent import load_intent
from automotive_workbench.can_io import sha256_file


def validate_declaration(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "vectors"}:
        raise ValueError("Communication declaration must be a closed object")
    if value["schema_version"] != "communication-vectors-0.1":
        raise ValueError("Unsupported communication declaration version")
    vectors = value["vectors"]
    if not isinstance(vectors, list) or not 1 <= len(vectors) <= 256:
        raise ValueError("Declare between 1 and 256 vectors")
    seen = set()
    for vector in vectors:
        if not isinstance(vector, dict) or set(vector) != {
            "id",
            "message",
            "direction",
            "signals",
            "timeout_seconds",
        }:
            raise ValueError(
                "Vector must declare id, message, direction, signals and timeout_seconds"
            )
        identity = vector["id"]
        if not isinstance(identity, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", identity
        ):
            raise ValueError("Vector ID must be a portable identifier")
        if identity in seen:
            raise ValueError("Vector IDs must be unique")
        seen.add(identity)
        if not isinstance(vector["message"], str) or not vector["message"].strip():
            raise ValueError("Vector message must be non-empty")
        if vector["direction"] not in ("tx", "rx"):
            raise ValueError("Vector direction must be tx or rx")
        timeout = vector["timeout_seconds"]
        if type(timeout) not in (int, float) or not 0 < timeout <= 5:
            raise ValueError("Vector timeout must be a finite number in (0, 5]")
        signals = vector["signals"]
        if not isinstance(signals, dict) or not signals:
            raise ValueError("Vector signals must be a non-empty object")
        for name, number in signals.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Signal names must be non-empty")
            if type(number) not in (int, float):
                raise ValueError("Signal values must be finite numbers, not booleans")
            try:
                finite = math.isfinite(number)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError("Signal values must be finite numbers")
    return value


def load_declaration(path: Path) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON member: {key}")
            result[key] = value
        return result

    return validate_declaration(
        json.loads(
            path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object
        )
    )


def compile_plan(
    database: Any, intent: dict[str, Any], declaration: Any
) -> dict[str, Any]:
    """Pure compilation; quantization follows cantools encode/decode raw integers.

    No arbitrary epsilon is used: expected physical values come from the encoded
    payload, and consumers can compare expected_raw_signals exactly.
    """
    declaration = validate_declaration(declaration)
    ecu = intent.get("local_ecu")
    if not isinstance(ecu, str) or not ecu.strip():
        raise ValueError("A local_ecu in the BSW intent is required")
    messages = {message.name: message for message in database.messages}
    if len(messages) != len(database.messages):
        raise ValueError("DBC message names must be unique")
    ids = [
        (message.frame_id, message.is_extended_frame) for message in database.messages
    ]
    if len(set(ids)) != len(ids):
        raise ValueError("DBC frame identities must be unique")
    declared_messages: dict[str, Any] = {}
    for item in intent["messages"]:
        name = item["dbc_message"]
        if name in declared_messages:
            raise ValueError("Intent message identities must be unique")
        declared_messages[name] = item
    vectors = []
    for vector in declaration["vectors"]:
        name = vector["message"]
        message = messages.get(name)
        expected = declared_messages.get(name)
        if message is None or expected is None:
            raise ValueError(f"Message must exist in DBC and intent: {name}")
        if (
            message.is_fd
            or message.length > 8
            or message.length < 1
            or message.is_container
            or message.is_multiplexed()
            or any(
                signal.is_multiplexer or signal.multiplexer_signal is not None
                for signal in message.signals
            )
        ):
            raise ValueError(
                f"Only non-multiplexed classic CAN messages are supported: {name}"
            )
        if any(signal.is_float for signal in message.signals):
            raise ValueError(f"Floating-point wire signals are unsupported: {name}")
        direction = vector["direction"]
        dbc_direction = (
            "tx"
            if ecu in message.senders
            else "rx"
            if all(ecu in signal.receivers for signal in message.signals)
            else None
        )
        if direction != expected.get("direction") or direction != dbc_direction:
            raise ValueError(f"Direction disagrees with intent or DBC: {name}")
        if (
            expected.get("can_id") != message.frame_id
            or expected.get("dlc") != message.length
        ):
            raise ValueError(f"Frame identity disagrees with intent: {name}")
        for signal in intent["signals"]:
            if signal["dbc_message"] == name and signal.get("direction") != direction:
                raise ValueError(f"Signal direction disagrees with vector: {name}")
        if set(vector["signals"]) != {signal.name for signal in message.signals}:
            raise ValueError(f"Supply exactly all DBC signals: {name}")
        try:
            payload = message.encode(vector["signals"], strict=True)
            raw = message.decode(payload, decode_choices=False, scaling=False)
            physical = message.decode(payload, decode_choices=False)
            if not all(math.isfinite(value) for value in physical.values()):
                raise ValueError("Non-finite decoded value")
        except Exception as exc:
            raise ValueError(
                f"Vector cannot be encoded: {vector['id']}: {exc}"
            ) from exc
        vectors.append(
            {
                "id": vector["id"],
                "message": name,
                "direction": direction,
                "signals": dict(vector["signals"]),
                "timeout_seconds": vector["timeout_seconds"],
                "frame_id": message.frame_id,
                "is_extended_id": message.is_extended_frame,
                "dlc": message.length,
                "payload_hex": payload.hex(),
                "expected_raw_signals": raw,
                "expected_signals": physical,
            }
        )
    return {"local_ecu": ecu, "vectors": vectors}


def preflight_communication(
    dbc: Path, intent: Path, declaration: Path
) -> dict[str, Any]:
    """Read-only entry point. Static mapping and all vectors precede any execution."""
    values = load_declaration(declaration)
    mapping = validate_dbc_intent(dbc, intent)
    if mapping["status"] != "passed":
        raise ValueError("Communication preflight requires a valid DBC/intent mapping")
    plan = compile_plan(_load_dbc(dbc), load_intent(intent), values)
    return {
        "artifact_type": "communication-plan",
        "schema_version": "communication-plan-0.1",
        "source_artifacts": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in (dbc, intent, declaration)
        ],
        **plan,
    }
