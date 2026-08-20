from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automotive_workbench.dtc_intent import load_dtc_intent


SUPPORTED_SCHEMA_VERSION = "uds-intent-0.1"
SUPPORTED_ADDRESSING = {"normal_11bit"}
SUPPORTED_SERVICES = {"ReadDataByIdentifier", "ReadDTCInformation", "ClearDiagnosticInformation"}
SUPPORTED_CODECS = {"ascii", "uint8", "uint16", "uint32", "raw"}
SUPPORTED_EXPECTATIONS = {"positive", "negative_response", "timeout", "malformed_payload"}


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"UDS intent requires {name} object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"UDS intent requires {name} list")
    return value


def _require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"UDS intent {name} must be an integer in range {minimum}..{maximum}")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"UDS intent requires non-empty {name}")
    return value


def load_uds_intent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError("Unsupported or missing uds-intent schema_version")
    _require_string(payload.get("ecu"), "ecu")
    dtc_codes: set[int] = set()
    if "dtc_intent" in payload:
        dtc_reference = _require_string(payload.get("dtc_intent"), "dtc_intent")
        dtc_payload = load_dtc_intent(path.parent / dtc_reference)
        dtc_codes = {int(item["code"]) for item in dtc_payload["dtcs"]}

    transport = _require_dict(payload.get("transport"), "transport")
    addressing = transport.get("addressing")
    if addressing not in SUPPORTED_ADDRESSING:
        raise ValueError(f"Unsupported UDS addressing: {addressing}")
    request_id = _require_int(transport.get("request_id"), "transport.request_id", 0, 0x7FF)
    response_id = _require_int(transport.get("response_id"), "transport.response_id", 0, 0x7FF)
    if request_id == response_id:
        raise ValueError("UDS intent request_id and response_id must differ")
    tx_data_length = _require_int(transport.get("tx_data_length"), "transport.tx_data_length", 1, 8)
    if tx_data_length != 8:
        raise ValueError("UDS intent currently supports only classic CAN tx_data_length=8")

    dids = _require_list(payload.get("dids"), "dids")
    did_ids: set[int] = set()
    for index, item in enumerate(dids):
        did = _require_dict(item, f"dids[{index}]")
        did_id = _require_int(did.get("id"), f"dids[{index}].id", 0, 0xFFFF)
        if did_id in did_ids:
            raise ValueError(f"Duplicate DID id: 0x{did_id:04X}")
        did_ids.add(did_id)
        _require_string(did.get("name"), f"dids[{index}].name")
        codec = did.get("codec")
        if codec not in SUPPORTED_CODECS:
            raise ValueError(f"Unsupported DID codec: {codec}")
        _require_int(did.get("length"), f"dids[{index}].length", 1, 4095)

    scenarios = _require_list(payload.get("scenarios"), "scenarios")
    scenario_names: set[str] = set()
    for index, item in enumerate(scenarios):
        scenario = _require_dict(item, f"scenarios[{index}]")
        name = _require_string(scenario.get("name"), f"scenarios[{index}].name")
        if name in scenario_names:
            raise ValueError(f"Duplicate UDS scenario name: {name}")
        scenario_names.add(name)
        service = scenario.get("service")
        if service not in SUPPORTED_SERVICES:
            raise ValueError(f"Unsupported UDS service: {service}")
        expected = scenario.get("expected", "positive")
        if expected not in SUPPORTED_EXPECTATIONS:
            raise ValueError(f"Unsupported UDS scenario expectation: {expected}")
        if service != "ReadDataByIdentifier" and expected != "positive":
            raise ValueError(f"{service} currently supports only positive expectation")
        if service == "ReadDataByIdentifier":
            did_id = _require_int(scenario.get("did"), f"scenarios[{index}].did", 0, 0xFFFF)
            if expected == "positive" and did_id not in did_ids:
                raise ValueError(f"Positive UDS scenario references unknown DID: 0x{did_id:04X}")
        elif service == "ReadDTCInformation":
            if scenario.get("subfunction") != "reportDTCByStatusMask":
                raise ValueError("ReadDTCInformation currently supports only reportDTCByStatusMask")
            _require_int(scenario.get("status_mask"), f"scenarios[{index}].status_mask", 1, 0xFF)
            expected_records = _require_list(
                scenario.get("expected_dtc_records"),
                f"scenarios[{index}].expected_dtc_records",
            )
            expected_codes: set[int] = set()
            for record_index, record in enumerate(expected_records):
                expected_record = _require_dict(
                    record,
                    f"scenarios[{index}].expected_dtc_records[{record_index}]",
                )
                dtc_code = _require_int(
                    expected_record.get("code"),
                    f"scenarios[{index}].expected_dtc_records[{record_index}].code",
                    0,
                    0xFFFFFF,
                )
                if dtc_code not in dtc_codes:
                    raise ValueError(f"UDS scenario references unknown DTC: 0x{dtc_code:06X}")
                if dtc_code in expected_codes:
                    raise ValueError(f"Duplicate expected DTC record: 0x{dtc_code:06X}")
                expected_codes.add(dtc_code)
                _require_int(
                    expected_record.get("status"),
                    f"scenarios[{index}].expected_dtc_records[{record_index}].status",
                    0,
                    0xFF,
                )
        else:
            group = _require_int(scenario.get("group"), f"scenarios[{index}].group", 0, 0xFFFFFF)
            if not dtc_codes:
                raise ValueError("ClearDiagnosticInformation requires dtc_intent")
            if group != 0xFFFFFF and group not in dtc_codes:
                raise ValueError(f"ClearDiagnosticInformation references unknown group: 0x{group:06X}")
        if expected == "negative_response":
            _require_string(scenario.get("nrc"), f"scenarios[{index}].nrc")
        if expected == "malformed_payload":
            did_id = _require_int(scenario.get("did"), f"scenarios[{index}].did", 0, 0xFFFF)
            if did_id not in did_ids:
                raise ValueError(f"Malformed UDS scenario references unknown DID: 0x{did_id:04X}")
            malformed_hex = _require_string(
                scenario.get("response_payload_hex"),
                f"scenarios[{index}].response_payload_hex",
            )
            try:
                bytes.fromhex(malformed_hex)
            except ValueError as exc:
                raise ValueError(
                    f"UDS scenario {name} response_payload_hex must be hexadecimal"
                ) from exc

    return payload


def summarize_uds_intent(path: Path) -> dict[str, Any]:
    payload = load_uds_intent(path)
    transport = payload["transport"]
    dids = payload["dids"]
    scenarios = payload["scenarios"]
    return {
        "artifact_type": "uds-intent-summary",
        "status": "passed",
        "schema_version": payload["schema_version"],
        "model_status": payload["model_status"],
        "ecu": payload["ecu"],
        "transport": {
            "addressing": transport["addressing"],
            "request_id": transport["request_id"],
            "request_id_hex": f"0x{transport['request_id']:03X}",
            "response_id": transport["response_id"],
            "response_id_hex": f"0x{transport['response_id']:03X}",
            "tx_data_length": transport["tx_data_length"],
        },
        "did_count": len(dids),
        "dids": [
            {
                "id": did["id"],
                "id_hex": f"0x{did['id']:04X}",
                "name": did["name"],
                "codec": did["codec"],
                "length": did["length"],
                "canonical_signal": did.get("canonical_signal", ""),
            }
            for did in dids
        ],
        "scenario_count": len(scenarios),
        "scenarios": [
            {
                "name": scenario["name"],
                "service": scenario["service"],
                "did": scenario.get("did"),
                "did_hex": f"0x{scenario['did']:04X}" if "did" in scenario else "",
                "status_mask_hex": f"0x{scenario['status_mask']:02X}" if "status_mask" in scenario else "",
                "group_hex": f"0x{scenario['group']:06X}" if "group" in scenario else "",
                "expected": scenario.get("expected", "positive"),
                "nrc": scenario.get("nrc", ""),
            }
            for scenario in scenarios
        ],
    }
