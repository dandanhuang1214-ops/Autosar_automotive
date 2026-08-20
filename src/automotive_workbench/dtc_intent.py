from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMA_VERSION = "dtc-intent-0.1"
SUPPORTED_EVENTS = {"fault_absent", "fault_present", "read_dtc", "clear_dtc"}
SUPPORTED_STATES = {"absent", "pending", "confirmed", "healing", "healed"}
SUPPORTED_CYCLE_EVENTS = {
    "operation_cycle_start",
    "operation_cycle_end",
    "fault_present",
    "fault_absent",
    "read_snapshot",
}
SUPPORTED_CYCLE_STATES = {*SUPPORTED_STATES, "aged_out"}


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
        _integer(item.get("aging_threshold"), f"dtcs[{index}].aging_threshold", 1, 255)
        initial_status = _integer(
            item.get("uds_initial_status"), f"dtcs[{index}].uds_initial_status", 0, 0xFF
        )
        if initial_status & ~availability_mask:
            raise ValueError(f"DTC 0x{code:06X} initial status uses unavailable bits")
        snapshot = item.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError(f"DTC intent requires dtcs[{index}].snapshot object")
        if snapshot.get("trigger") != "confirmed":
            raise ValueError("DTC snapshot currently supports only confirmed trigger")
        _integer(snapshot.get("record_number"), f"dtcs[{index}].snapshot.record_number", 1, 0xFE)
        snapshot_dids: set[int] = set()
        for did_index, did_item in enumerate(
            _list(snapshot.get("dids"), f"dtcs[{index}].snapshot.dids")
        ):
            if not isinstance(did_item, dict):
                raise ValueError(f"DTC intent requires snapshot did object at index {did_index}")
            did = _integer(did_item.get("did"), "snapshot.did", 0, 0xFFFF)
            if did in snapshot_dids:
                raise ValueError(f"Duplicate snapshot DID: 0x{did:04X}")
            snapshot_dids.add(did)
            if did_item.get("codec") != "uint8" or did_item.get("length") != 1:
                raise ValueError("DTC snapshot currently supports only uint8 length=1")
            _integer(did_item.get("value"), "snapshot.value", 0, 0xFF)

        extended_data = item.get("extended_data")
        if not isinstance(extended_data, dict):
            raise ValueError(f"DTC intent requires dtcs[{index}].extended_data object")
        if extended_data.get("retention") != "until_aged_or_cleared":
            raise ValueError("DTC extended data currently supports only until_aged_or_cleared retention")
        record_numbers: set[int] = set()
        sources: set[str] = set()
        for record_index, record in enumerate(
            _list(extended_data.get("records"), f"dtcs[{index}].extended_data.records")
        ):
            if not isinstance(record, dict):
                raise ValueError(f"DTC intent requires extended data record object at index {record_index}")
            record_number = _integer(
                record.get("record_number"), "extended_data.record_number", 1, 0xFE
            )
            if record_number in record_numbers:
                raise ValueError(f"Duplicate extended data record: 0x{record_number:02X}")
            record_numbers.add(record_number)
            _string(record.get("name"), "extended_data.name")
            source = record.get("source")
            if source not in {"occurrence_counter", "aging_counter"}:
                raise ValueError(f"Unsupported extended data source: {source}")
            if source in sources:
                raise ValueError(f"Duplicate extended data source: {source}")
            sources.add(str(source))
            if record.get("length") != 1:
                raise ValueError("DTC extended data currently supports only uint8 length=1")
            _integer(record.get("uds_initial_value"), "extended_data.uds_initial_value", 0, 0xFF)

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

    cycle_names: set[str] = set()
    for index, item in enumerate(_list(payload.get("cycle_experiments"), "cycle_experiments")):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires cycle_experiments[{index}] object")
        name = _string(item.get("name"), f"cycle_experiments[{index}].name")
        if name in cycle_names:
            raise ValueError(f"Duplicate DTC cycle experiment name: {name}")
        cycle_names.add(name)
        code = _integer(item.get("dtc"), f"cycle_experiments[{index}].dtc", 0, 0xFFFFFF)
        if code not in codes:
            raise ValueError(f"DTC cycle experiment references unknown code: 0x{code:06X}")
        for step_index, step in enumerate(
            _list(item.get("steps"), f"cycle_experiments[{index}].steps")
        ):
            if not isinstance(step, dict):
                raise ValueError(
                    f"DTC intent requires cycle_experiments[{index}].steps[{step_index}] object"
                )
            if step.get("event") not in SUPPORTED_CYCLE_EVENTS:
                raise ValueError(f"Unsupported DTC cycle event: {step.get('event')}")
            if step.get("expected_state") not in SUPPORTED_CYCLE_STATES:
                raise ValueError(f"Unsupported DTC cycle state: {step.get('expected_state')}")
            expected_status = _integer(step.get("expected_status"), "expected_status", 0, 0xFF)
            if expected_status & ~availability_mask:
                raise ValueError("DTC cycle step expected status uses unavailable bits")
            _integer(step.get("expected_aging_counter"), "expected_aging_counter", 0, 0xFF)
            for field in ("expected_snapshot_stored", "expected_cycle_active"):
                if not isinstance(step.get(field), bool):
                    raise ValueError(f"DTC cycle step requires boolean {field}")
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
                "aging_threshold": item["aging_threshold"],
                "snapshot_record_number": item["snapshot"]["record_number"],
            }
            for item in payload["dtcs"]
        ],
        "experiment_count": len(payload["experiments"]),
        "experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["experiments"]
        ],
        "cycle_experiment_count": len(payload["cycle_experiments"]),
        "cycle_experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["cycle_experiments"]
        ],
    }
