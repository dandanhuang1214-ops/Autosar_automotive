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
SUPPORTED_RESET_EVENTS = {
    "operation_cycle_start",
    "operation_cycle_end",
    "fault_present",
    "flush",
    "hard_reset",
    "clear_dtc",
}
SUPPORTED_RESET_STATES = {"absent", "pending", "confirmed"}
SUPPORTED_PERSISTENCE_FAULT_EVENTS = {
    "operation_cycle_start",
    "operation_cycle_end",
    "fault_present",
    "flush",
    "inject_flush_failure",
    "corrupt_mirror",
    "hard_reset",
}
SUPPORTED_PERSISTENCE_FINDINGS = {
    "",
    "DTC-PERSISTENCE-FLUSH-FAILED",
    "DTC-PERSISTENCE-MIRROR-CORRUPTED",
    "DTC-PERSISTENCE-RESTORE-FAILED",
}
SUPPORTED_REDUNDANCY_EVENTS = {
    "operation_cycle_start",
    "operation_cycle_end",
    "fault_present",
    "flush",
    "corrupt_copy_a",
    "hard_reset",
}
SUPPORTED_REDUNDANCY_FINDINGS = {
    "",
    "DTC-REDUNDANCY-LOSS",
    "DTC-REDUNDANCY-COPY-CORRUPTED",
    "DTC-REDUNDANCY-ARBITRATION-FAILED",
    "DTC-REDUNDANCY-RESTORE-FAILED",
}
SUPPORTED_REDUNDANCY_REPAIR_EVENTS = {
    "operation_cycle_start",
    "operation_cycle_end",
    "fault_present",
    "flush",
    "stage_flush",
    "interrupt_write",
    "hard_reset",
    "repair",
    "stage_repair",
    "interrupt_repair",
}
SUPPORTED_REDUNDANCY_REPAIR_OUTCOMES = {
    "",
    "staged",
    "committed",
    "no-op",
    "refused",
    "interrupted",
}
SUPPORTED_REDUNDANCY_REPAIR_FINDINGS = {
    *SUPPORTED_REDUNDANCY_FINDINGS,
    "DTC-REDUNDANCY-WRITE-INTERRUPTED",
    "DTC-REDUNDANCY-REPAIR-INTERRUPTED",
    "DTC-REDUNDANCY-REPAIR-REFUSED",
}


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

        persistence = item.get("persistence")
        if not isinstance(persistence, dict):
            raise ValueError(f"DTC intent requires dtcs[{index}].persistence object")
        if persistence.get("retained_data") != ["status", "snapshot", "extended_data"]:
            raise ValueError(
                "DTC persistence currently requires status, snapshot and extended_data retention"
            )
        if persistence.get("flush_event") != "explicit":
            raise ValueError("DTC persistence currently requires explicit flush_event")
        if persistence.get("clear_updates_persistent_memory") is not True:
            raise ValueError("DTC persistence requires clear_updates_persistent_memory=true")

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
                raise ValueError("DTC lifecycle step expected status uses unavailable bits")
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

    reset_names: set[str] = set()
    for index, item in enumerate(_list(payload.get("reset_experiments"), "reset_experiments")):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires reset_experiments[{index}] object")
        name = _string(item.get("name"), f"reset_experiments[{index}].name")
        if name in reset_names:
            raise ValueError(f"Duplicate DTC reset experiment name: {name}")
        reset_names.add(name)
        code = _integer(item.get("dtc"), f"reset_experiments[{index}].dtc", 0, 0xFFFFFF)
        if code not in codes:
            raise ValueError(f"DTC reset experiment references unknown code: 0x{code:06X}")
        for step_index, step in enumerate(
            _list(item.get("steps"), f"reset_experiments[{index}].steps")
        ):
            if not isinstance(step, dict):
                raise ValueError(
                    f"DTC intent requires reset_experiments[{index}].steps[{step_index}] object"
                )
            if step.get("event") not in SUPPORTED_RESET_EVENTS:
                raise ValueError(f"Unsupported DTC reset event: {step.get('event')}")
            if step.get("expected_runtime_state") not in SUPPORTED_RESET_STATES:
                raise ValueError(
                    f"Unsupported DTC reset state: {step.get('expected_runtime_state')}"
                )
            for field in ("expected_runtime_status", "expected_persistent_status"):
                status = _integer(step.get(field), field, 0, 0xFF)
                if status & ~availability_mask:
                    raise ValueError(f"DTC reset step {field} uses unavailable bits")
            for field in (
                "expected_runtime_snapshot_stored",
                "expected_persistent_snapshot_stored",
                "expected_runtime_extended_data_stored",
                "expected_persistent_extended_data_stored",
            ):
                if not isinstance(step.get(field), bool):
                    raise ValueError(f"DTC reset step requires boolean {field}")

    fault_names: set[str] = set()
    for index, item in enumerate(
        _list(payload.get("persistence_fault_experiments"), "persistence_fault_experiments")
    ):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires persistence_fault_experiments[{index}] object")
        name = _string(item.get("name"), f"persistence_fault_experiments[{index}].name")
        if name in fault_names:
            raise ValueError(f"Duplicate DTC persistence fault experiment name: {name}")
        fault_names.add(name)
        code = _integer(
            item.get("dtc"), f"persistence_fault_experiments[{index}].dtc", 0, 0xFFFFFF
        )
        if code not in codes:
            raise ValueError(f"DTC persistence fault experiment references unknown code: 0x{code:06X}")
        for step_index, step in enumerate(
            _list(item.get("steps"), f"persistence_fault_experiments[{index}].steps")
        ):
            if not isinstance(step, dict):
                raise ValueError(
                    f"DTC intent requires persistence_fault_experiments[{index}].steps[{step_index}] object"
                )
            if step.get("event") not in SUPPORTED_PERSISTENCE_FAULT_EVENTS:
                raise ValueError(f"Unsupported DTC persistence fault event: {step.get('event')}")
            if step.get("expected_runtime_state") not in SUPPORTED_RESET_STATES:
                raise ValueError(
                    f"Unsupported DTC persistence fault state: {step.get('expected_runtime_state')}"
                )
            for field in ("expected_runtime_status", "expected_persistent_status"):
                status = _integer(step.get(field), field, 0, 0xFF)
                if status & ~availability_mask:
                    raise ValueError(f"DTC persistence fault step {field} uses unavailable bits")
            for field in (
                "expected_runtime_snapshot_stored",
                "expected_persistent_snapshot_stored",
                "expected_runtime_extended_data_stored",
                "expected_persistent_extended_data_stored",
                "expected_mirror_integrity",
            ):
                if not isinstance(step.get(field), bool):
                    raise ValueError(f"DTC persistence fault step requires boolean {field}")
            if step.get("expected_finding") not in SUPPORTED_PERSISTENCE_FINDINGS:
                raise ValueError(
                    f"Unsupported DTC persistence expected Finding: {step.get('expected_finding')}"
                )

    redundancy_names: set[str] = set()
    for index, item in enumerate(
        _list(payload.get("redundancy_experiments"), "redundancy_experiments")
    ):
        if not isinstance(item, dict):
            raise ValueError(f"DTC intent requires redundancy_experiments[{index}] object")
        name = _string(item.get("name"), f"redundancy_experiments[{index}].name")
        if name in redundancy_names:
            raise ValueError(f"Duplicate DTC redundancy experiment name: {name}")
        redundancy_names.add(name)
        code = _integer(item.get("dtc"), f"redundancy_experiments[{index}].dtc", 0, 0xFFFFFF)
        if code not in codes:
            raise ValueError(f"DTC redundancy experiment references unknown code: 0x{code:06X}")
        for step_index, step in enumerate(
            _list(item.get("steps"), f"redundancy_experiments[{index}].steps")
        ):
            if not isinstance(step, dict):
                raise ValueError(
                    f"DTC intent requires redundancy_experiments[{index}].steps[{step_index}] object"
                )
            if step.get("event") not in SUPPORTED_REDUNDANCY_EVENTS:
                raise ValueError(f"Unsupported DTC redundancy event: {step.get('event')}")
            if step.get("expected_runtime_state") not in SUPPORTED_RESET_STATES:
                raise ValueError(
                    f"Unsupported DTC redundancy state: {step.get('expected_runtime_state')}"
                )
            for field in (
                "expected_runtime_status",
                "expected_copy_a_status",
                "expected_copy_b_status",
            ):
                status = _integer(step.get(field), field, 0, 0xFF)
                if status & ~availability_mask:
                    raise ValueError(f"DTC redundancy step {field} uses unavailable bits")
            for field in ("expected_copy_a_generation", "expected_copy_b_generation"):
                _integer(step.get(field), field, 0, 0x7FFFFFFF)
            for field in ("expected_copy_a_integrity", "expected_copy_b_integrity"):
                if not isinstance(step.get(field), bool):
                    raise ValueError(f"DTC redundancy step requires boolean {field}")
            if step.get("expected_selected_copy") not in {"", "A", "B"}:
                raise ValueError(
                    f"Unsupported DTC redundancy selected copy: {step.get('expected_selected_copy')}"
                )
            if step.get("expected_finding") not in SUPPORTED_REDUNDANCY_FINDINGS:
                raise ValueError(
                    f"Unsupported DTC redundancy expected Finding: {step.get('expected_finding')}"
                )

    repair_names: set[str] = set()
    for index, item in enumerate(
        _list(
            payload.get("redundancy_repair_experiments"),
            "redundancy_repair_experiments",
        )
    ):
        if not isinstance(item, dict):
            raise ValueError(
                f"DTC intent requires redundancy_repair_experiments[{index}] object"
            )
        name = _string(
            item.get("name"), f"redundancy_repair_experiments[{index}].name"
        )
        if name in repair_names:
            raise ValueError(f"Duplicate DTC redundancy repair experiment name: {name}")
        repair_names.add(name)
        code = _integer(
            item.get("dtc"),
            f"redundancy_repair_experiments[{index}].dtc",
            0,
            0xFFFFFF,
        )
        if code not in codes:
            raise ValueError(
                f"DTC redundancy repair experiment references unknown code: 0x{code:06X}"
            )
        for step_index, step in enumerate(
            _list(
                item.get("steps"),
                f"redundancy_repair_experiments[{index}].steps",
            )
        ):
            if not isinstance(step, dict):
                raise ValueError(
                    "DTC intent requires redundancy_repair_experiments"
                    f"[{index}].steps[{step_index}] object"
                )
            if step.get("event") not in SUPPORTED_REDUNDANCY_REPAIR_EVENTS:
                raise ValueError(
                    f"Unsupported DTC redundancy repair event: {step.get('event')}"
                )
            if step.get("expected_runtime_state") not in SUPPORTED_RESET_STATES:
                raise ValueError(
                    "Unsupported DTC redundancy repair state: "
                    f"{step.get('expected_runtime_state')}"
                )
            for field in (
                "expected_runtime_status",
                "expected_copy_a_status",
                "expected_copy_b_status",
            ):
                status = _integer(step.get(field), field, 0, 0xFF)
                if status & ~availability_mask:
                    raise ValueError(
                        f"DTC redundancy repair step {field} uses unavailable bits"
                    )
            for field in ("expected_copy_a_generation", "expected_copy_b_generation"):
                _integer(step.get(field), field, 0, 0x7FFFFFFF)
            for field in (
                "expected_copy_a_integrity",
                "expected_copy_b_integrity",
                "expected_copy_a_committed",
                "expected_copy_b_committed",
            ):
                if not isinstance(step.get(field), bool):
                    raise ValueError(
                        f"DTC redundancy repair step requires boolean {field}"
                    )
            if step.get("expected_selected_copy") not in {"", "A", "B"}:
                raise ValueError(
                    "Unsupported DTC redundancy repair selected copy: "
                    f"{step.get('expected_selected_copy')}"
                )
            if step.get("expected_repair_outcome") not in SUPPORTED_REDUNDANCY_REPAIR_OUTCOMES:
                raise ValueError(
                    "Unsupported DTC redundancy repair outcome: "
                    f"{step.get('expected_repair_outcome')}"
                )
            if step.get("expected_finding") not in SUPPORTED_REDUNDANCY_REPAIR_FINDINGS:
                raise ValueError(
                    "Unsupported DTC redundancy repair expected Finding: "
                    f"{step.get('expected_finding')}"
                )
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
        "reset_experiment_count": len(payload["reset_experiments"]),
        "reset_experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["reset_experiments"]
        ],
        "persistence_fault_experiment_count": len(payload["persistence_fault_experiments"]),
        "persistence_fault_experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["persistence_fault_experiments"]
        ],
        "redundancy_experiment_count": len(payload["redundancy_experiments"]),
        "redundancy_experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["redundancy_experiments"]
        ],
        "redundancy_repair_experiment_count": len(payload["redundancy_repair_experiments"]),
        "redundancy_repair_experiments": [
            {"name": item["name"], "dtc_hex": f"0x{item['dtc']:06X}", "step_count": len(item["steps"])}
            for item in payload["redundancy_repair_experiments"]
        ],
    }
