from __future__ import annotations

import json
import re
from math import isclose
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.bsw_intent import load_intent
from automotive_workbench.domain import Finding


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _range(value: Any) -> tuple[float, float] | None:
    text = str(value or "").strip()
    number = r"[-+]?\d+(?:\.\d+)?"
    match = re.fullmatch(
        rf"[\[\(]?\s*({number})\s*(?:\.\.|,|\||\s+-\s+|(?<=\d)-(?=\d))\s*({number})\s*[\]\)]?",
        text,
    )
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _same_number(left: Any, right: Any) -> bool:
    left_number, right_number = _number(left), _number(right)
    return left_number is not None and right_number is not None and isclose(
        left_number, right_number, rel_tol=1e-9, abs_tol=1e-9
    )


def load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload.get("signals"), list):
        raise ValueError("Generate-Arxml canonical contract requires a signals list")
    return payload


def validate_contract_mapping(dbc_path: Path, contract_path: Path, intent_path: Path) -> dict[str, Any]:
    database = _load_dbc(dbc_path)
    contract = load_contract(contract_path)
    intent = load_intent(intent_path)
    dbc_messages = {message.name: message for message in database.messages}
    contract_signals = {
        str(signal.get("signal_name") or ""): signal
        for signal in contract["signals"]
        if isinstance(signal, dict)
    }
    findings: list[Finding] = []

    def add(code: str, message: str, field: str, location: str) -> None:
        findings.append(Finding(
            code=code,
            severity="ERROR",
            message=message,
            source_artifact=str(contract_path),
            kind="cross-stage-mapping",
            field=field,
            location=location,
        ))

    checked = 0
    for mapping in intent["signals"]:
        dbc_message_name = str(mapping.get("dbc_message") or "")
        dbc_signal_name = str(mapping.get("dbc_signal") or "")
        canonical_name = str(mapping.get("canonical_signal") or "")
        message = dbc_messages.get(dbc_message_name)
        dbc_signal = next(
            (signal for signal in message.signals if signal.name == dbc_signal_name), None
        ) if message else None
        canonical = contract_signals.get(canonical_name)
        location = f"{dbc_message_name}.{dbc_signal_name} -> {canonical_name}"
        if dbc_signal is None:
            add("MAP-DBC-SIGNAL-MISSING", f"Mapped DBC signal does not exist: {dbc_message_name}.{dbc_signal_name}", "dbc_signal", location)
            continue
        if canonical is None:
            add("MAP-CANONICAL-SIGNAL-MISSING", f"Mapped canonical signal does not exist: {canonical_name}", "canonical_signal", location)
            continue
        checked += 1
        comparisons = (
            ("resolution", dbc_signal.scale, canonical.get("resolution")),
            ("offset", dbc_signal.offset, canonical.get("offset")),
        )
        for field, dbc_value, canonical_value in comparisons:
            if not _same_number(dbc_value, canonical_value):
                add("MAP-NUMERIC-MISMATCH", f"{field}: DBC={dbc_value!r}, canonical={canonical_value!r}", field, location)
        if (dbc_signal.unit or "") != str(canonical.get("unit") or ""):
            add("MAP-UNIT-MISMATCH", f"unit: DBC={dbc_signal.unit or ''!r}, canonical={canonical.get('unit') or ''!r}", "unit", location)
        canonical_range = _range(canonical.get("physical_range"))
        dbc_range = None if dbc_signal.minimum is None or dbc_signal.maximum is None else (
            float(dbc_signal.minimum), float(dbc_signal.maximum)
        )
        if canonical_range is None:
            add("MAP-RANGE-UNPARSEABLE", f"Cannot parse canonical physical_range: {canonical.get('physical_range')!r}", "physical_range", location)
        elif dbc_range is None or any(
            not isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
            for left, right in zip(dbc_range, canonical_range)
        ):
            add("MAP-RANGE-MISMATCH", f"physical range: DBC={dbc_range!r}, canonical={canonical_range!r}", "physical_range", location)

    return {
        "artifact_type": "dbc.canonical.intent_validation",
        "dbc": str(dbc_path),
        "contract": str(contract_path),
        "intent": str(intent_path),
        "status": "passed" if not findings else "failed",
        "mapping_count": len(intent["signals"]),
        "checked_count": checked,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
        "not_inferred": [
            "ASW direction/provider/consumer from DBC",
            "vendor ECUC container paths or generated BSW configuration",
        ],
    }
