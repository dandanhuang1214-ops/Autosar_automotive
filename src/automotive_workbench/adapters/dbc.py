from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Any

from automotive_workbench.bsw_intent import load_intent
from automotive_workbench.domain import Finding


def _cantools() -> Any:
    try:
        import cantools
    except ImportError as exc:
        raise RuntimeError(
            'DBC support requires the optional dependency: pip install -e ".[can]"'
        ) from exc
    return cantools


def _load_dbc(path: Path) -> Any:
    return _cantools().database.load_file(str(path))


def inspect_dbc(path: Path) -> dict[str, Any]:
    database = _load_dbc(path)
    return {
        "artifact_type": "dbc",
        "source": str(path),
        "message_count": len(database.messages),
        "messages": [
            {
                "name": message.name,
                "frame_id": message.frame_id,
                "dlc": message.length,
                "signals": [
                    {
                        "name": signal.name,
                        "start_bit": signal.start,
                        "bit_length": signal.length,
                        "byte_order": signal.byte_order,
                        "is_signed": signal.is_signed,
                        "scale": signal.scale,
                        "offset": signal.offset,
                        "minimum": signal.minimum,
                        "maximum": signal.maximum,
                        "unit": signal.unit or "",
                    }
                    for signal in message.signals
                ],
            }
            for message in database.messages
        ],
    }


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)
    return actual == expected


def validate_dbc_intent(dbc_path: Path, intent_path: Path) -> dict[str, Any]:
    database = _load_dbc(dbc_path)
    intent = load_intent(intent_path)
    dbc_messages = {message.name: message for message in database.messages}
    findings: list[Finding] = []

    def add(code: str, message: str, kind: str, field: str, location: str) -> None:
        findings.append(Finding(
            code=code,
            severity="ERROR",
            message=message,
            source_artifact=str(dbc_path),
            kind=kind,
            field=field,
            location=location,
        ))

    for expected in intent.get("messages", []):
        name = str(expected.get("dbc_message") or "")
        actual = dbc_messages.get(name)
        if actual is None:
            add("DBC-MESSAGE-MISSING", f"DBC message is missing: {name}", "message", "dbc_message", name)
            continue
        for field, actual_value, expected_key, code in (
            ("frame_id", actual.frame_id, "can_id", "DBC-FRAME-ID-MISMATCH"),
            ("dlc", actual.length, "dlc", "DBC-DLC-MISMATCH"),
        ):
            expected_value = expected.get(expected_key)
            if expected_value is not None and not _equal(actual_value, expected_value):
                add(code, f"{name}.{field}: DBC={actual_value!r}, intent={expected_value!r}", "message", field, name)

    intent_messages = {
        str(message.get("dbc_message") or ""): message
        for message in intent.get("messages", [])
        if isinstance(message, dict)
    }

    properties = (
        ("start_bit", "start"),
        ("bit_length", "length"),
        ("byte_order", "byte_order"),
        ("is_signed", "is_signed"),
        ("scale", "scale"),
        ("offset", "offset"),
        ("minimum", "minimum"),
        ("maximum", "maximum"),
        ("unit", "unit"),
    )
    for expected in intent["signals"]:
        message_name = str(expected.get("dbc_message") or "")
        signal_name = str(expected.get("dbc_signal") or "")
        intent_message = intent_messages.get(message_name)
        if intent_message is not None:
            for reference_field in ("i_pdu", "canif_pdu"):
                message_reference = intent_message.get(reference_field)
                signal_reference = expected.get(reference_field)
                if (
                    message_reference is not None
                    and signal_reference is not None
                    and message_reference != signal_reference
                ):
                    add(
                        "INTENT-CROSS-LEVEL-REFERENCE-MISMATCH",
                        (
                            f"{message_name}.{signal_name}.{reference_field}: "
                            f"message={message_reference!r}, signal={signal_reference!r}"
                        ),
                        "signal",
                        reference_field,
                        f"{message_name}.{signal_name}",
                    )
        message = dbc_messages.get(message_name)
        if message is None:
            continue
        actual_signal = next((signal for signal in message.signals if signal.name == signal_name), None)
        if actual_signal is None:
            add("DBC-SIGNAL-MISSING", f"DBC signal is missing: {message_name}.{signal_name}", "signal", "dbc_signal", f"{message_name}.{signal_name}")
            continue
        for intent_field, dbc_attr in properties:
            if intent_field not in expected:
                continue
            actual_value = getattr(actual_signal, dbc_attr)
            if intent_field == "unit":
                actual_value = actual_value or ""
            expected_value = expected[intent_field]
            if not _equal(actual_value, expected_value):
                add(
                    "DBC-SIGNAL-PROPERTY-MISMATCH",
                    f"{message_name}.{signal_name}.{intent_field}: DBC={actual_value!r}, intent={expected_value!r}",
                    "signal",
                    intent_field,
                    f"{message_name}.{signal_name}",
                )

    return {
        "artifact_type": "dbc.intent_validation",
        "dbc": str(dbc_path),
        "intent": str(intent_path),
        "status": "passed" if not findings else "failed",
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
