from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMA_VERSION = "dtc-intent-0.1"
SUPPORTED_EVENTS = {"fault_absent", "fault_present", "read_dtc", "clear_dtc"}
SUPPORTED_STATES = {"absent", "pending", "confirmed", "healing", "healed"}


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"DTC intent {name} must be an integer in range {minimum}..{maximum}")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"DTC intent requires non-empty {name}")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"DTC intent requires non-empty {name} list")
    return value


def load_dtc_intent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError("Unsupported or missing dtc-intent schema_version")
    _string(payload.get("ecu"), "ecu")
    availability_mask = _integer(
        payload.get("status_availability_mask", 0xFF), "status_availability_mask", 0, 0xFF
    )

    codes: set[int] = set()
    for index, item in enumerate(_list(payload.get("dtcs"), "dtcs")):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires dtcs[{index}] object")
        code = _integer(item.get("code"), f"dtcs[{index}].code", 0, 0xFFFFFF)
        if code in codes:
            raise ValueError(f"Duplicate DTC code: 0x{code:06X}")
        codes.add(code)
        _string(item.get("name"), f"dtcs[{index}].name")
        _integer(item.get("failure_threshold"), f"dtcs[{index}].failure_threshold", 1, 255)
        _integer(item.get("healing_threshold"), f"dtcs[{index}].healing_threshold", 1, 255)
        initial_status = _integer(
            item.get("uds_initial_status"), f"dtcs[{index}].uds_initial_status", 0, 0xFF
        )
        if initial_status & ~availability_mask:
            raise ValueError(f"DTC 0x{code:06X} initial status uses unavailable bits")

    names: set[str] = set()
    for index, item in enumerate(_list(payload.get("experiments"), "experiments")):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires experiments[{index}] object")
        name = _string(item.get("name"), f"experiments[{index}].name")
        if name in names:
            raise ValueError(f"Duplicate DTC experiment name: {name}")
        names.add(name)
        code = _integer(item.get("dtc"), f"experiments[{index}].dtc", 0, 0xFFFFFF)
        if code not in codes:
            raise ValueError(f"DTC experiment references unknown code: 0x{code:06X}")
        for step_index, step in enumerate(_list(item.get("steps"), f"experiments[{index}].steps")):
            if not isinstance(step, dict):
                raise ValueError(f"DTC intent requires experiments[{index}].steps[{step_index}] object")
            event = step.get("event")
            if event not in SUPPORTED_EVENTS:
                raise ValueError(f"Unsupported DTC lifecycle event: {event}")
            state = step.get("expected_state")
            if state not in SUPPORTED_STATES:
                raise ValueError(f"Unsupported DTC lifecycle state: {state}")
            expected_status = _integer(step.get("expected_status"), "expected_status", 0, 0xFF)
            if expected_status & ~availability_mask:
                raise ValueError(f"DTC lifecycle step expected status uses unavailable bits")
            if event == "read_dtc":
                _integer(step.get("status_mask"), "status_mask", 1, 0xFF)
    return payload


def summarize_dtc_intent(path: Path) -> dict[str, Any]:
    payload = load_dtc_intent(path)
    return {
        "artifact_type": "dtc-intent-summary",
        "status": "passed",
        "schema_version": payload["schema_version"],
        "model_status": payload["model_status"],
        "ecu": payload["ecu"],
        "dtc_count": len(payload["dtcs"]),
        "dtcs": [
            {
                "code": item["code"],
                "code_hex": f"0x{item['code']:06X}",
                "name": item["name"],
                "failure_threshold": item["failure_threshold"],
                "healing_threshold": item["healing_threshold"],
            }
            for item in payload["dtcs"]
        ],
        "experiment_count": len(payload["experiments"]),
        "experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["experiments"]
        ],
    }
