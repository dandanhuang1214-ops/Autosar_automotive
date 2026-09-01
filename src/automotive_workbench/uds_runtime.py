from __future__ import annotations

import json
import logging
import platform
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from importlib import metadata
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from automotive_workbench.can_backend import probe_can_backend
from automotive_workbench.applicability import build_runtime_applicability_profile
from automotive_workbench.can_io import (
    BusConfig,
    bus_isolation_evidence,
    exact_can_filters,
    open_bus,
)
from automotive_workbench.diag_intent import load_uds_intent
from automotive_workbench.domain import Finding
from automotive_workbench.dtc_intent import load_dtc_intent


def _diag_libs() -> tuple[Any, Any, Any, Any, Any]:
    try:
        import can
        import isotp
        from udsoncan import AsciiCodec
        from udsoncan.client import Client
        from udsoncan.connections import PythonIsoTpConnection
    except ImportError as exc:
        raise RuntimeError(
            'UDS runtime requires the optional dependency: pip install -e ".[diag]"'
        ) from exc
    return can, isotp, AsciiCodec, Client, PythonIsoTpConnection


def _package_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ""


def _module_file_exists(pattern: str) -> bool:
    module_dir = Path("/lib/modules") / platform.release()
    if not module_dir.is_dir():
        return False
    return any(module_dir.rglob(pattern))


def _kernel_isotp_probe(config: BusConfig) -> dict[str, Any]:
    evidence = {
        "required_for_user_space_stack": False,
        "platform": sys.platform,
        "module_loaded": False,
        "module_file_present": False,
    }
    if sys.platform != "linux":
        return evidence
    evidence["module_loaded"] = Path("/proc/modules").read_text(
        encoding="utf-8", errors="replace"
    ).find("can_isotp ") >= 0 if Path("/proc/modules").is_file() else False
    evidence["module_file_present"] = _module_file_exists("can-isotp.ko*")
    evidence["relevant_for_backend"] = config.interface == "socketcan"
    return evidence


def probe_uds_backend(config: BusConfig, output: Path | None = None) -> dict[str, Any]:
    dependencies = {
        "python_can": {
            "module": "can",
            "present": find_spec("can") is not None,
            "version": _package_version("python-can"),
        },
        "can_isotp": {
            "module": "isotp",
            "present": find_spec("isotp") is not None,
            "version": _package_version("can-isotp"),
        },
        "udsoncan": {
            "module": "udsoncan",
            "present": find_spec("udsoncan") is not None,
            "version": _package_version("udsoncan"),
        },
    }
    missing = [name for name, detail in dependencies.items() if not detail["present"]]
    can_probe = probe_can_backend(config, None)
    kernel_isotp = _kernel_isotp_probe(config)
    if missing:
        status = "blocked"
        reason = "missing_diag_dependency"
    elif can_probe["status"] != "available":
        status = "blocked"
        reason = can_probe.get("reason") or "can_backend_unavailable"
    else:
        status = "available"
        reason = ""
    result = {
        "artifact_type": "uds-backend-capability",
        "status": status,
        "reason": reason,
        "config": {
            "interface": config.interface,
            "channel": config.channel,
            "receive_own_messages": config.receive_own_messages,
            "fd": config.fd,
        },
        "dependencies": dependencies,
        "missing_dependencies": missing,
        "can_backend_probe": can_probe,
        "kernel_isotp": kernel_isotp,
        "transport_strategy": "udsoncan + can-isotp NotifierBasedCanStack + python-can BusConfig",
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "uds-backend-probe.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        markdown = [
            "# UDS Backend Probe",
            "",
            f"- Status: **{status}**",
            f"- Reason: `{reason or 'none'}`",
            f"- Interface: `{config.interface}`",
            f"- Channel: `{config.channel}`",
            f"- Transport strategy: `{result['transport_strategy']}`",
            "",
            "| Dependency | Present | Version |",
            "|---|---|---|",
        ]
        for name, detail in dependencies.items():
            markdown.append(f"| `{name}` | {detail['present']} | `{detail['version'] or 'unknown'}` |")
        markdown.extend([
            "",
            "## Backend",
            "",
            f"- CAN backend status: `{can_probe['status']}`",
            f"- CAN backend reason: `{can_probe.get('reason') or 'none'}`",
            f"- Kernel ISO-TP module loaded: `{kernel_isotp['module_loaded']}`",
            f"- Kernel ISO-TP module file present: `{kernel_isotp['module_file_present']}`",
            "",
            "Kernel ISO-TP is recorded for later Linux comparison. The current lab path uses user-space can-isotp over python-can.",
            "",
        ])
        (output / "uds-backend-probe.md").write_text("\n".join(markdown), encoding="utf-8")
    return result


def _request_payload(did: int) -> bytes:
    return bytes([0x22, (did >> 8) & 0xFF, did & 0xFF])


def _positive_response_payload(did: dict[str, Any]) -> bytes:
    did_id = int(did["id"])
    value = did.get("value")
    codec = did["codec"]
    length = int(did["length"])
    if codec == "ascii":
        data = str(value or "").encode("ascii")
    elif codec == "uint8":
        data = int(value).to_bytes(1, "big")
    elif codec == "uint16":
        data = int(value).to_bytes(2, "big")
    elif codec == "uint32":
        data = int(value).to_bytes(4, "big")
    elif codec == "raw":
        data = bytes.fromhex(str(value or ""))
    else:
        raise ValueError(f"Unsupported DID codec: {codec}")
    if len(data) != length:
        raise ValueError(f"DID 0x{did_id:04X} encoded length {len(data)} != declared length {length}")
    return bytes([0x62, (did_id >> 8) & 0xFF, did_id & 0xFF]) + data


def _client_codec(did: dict[str, Any], ascii_codec: Any) -> Any:
    codec = did["codec"]
    length = int(did["length"])
    if codec == "ascii":
        return ascii_codec(length)
    if codec == "uint8":
        return "B"
    if codec == "uint16":
        return ">H"
    if codec == "uint32":
        return ">L"
    if codec == "raw":
        return f"{length}s"
    raise ValueError(f"Unsupported DID codec: {codec}")


class _UdsResponder:
    def __init__(
        self,
        stack: Any,
        dids_by_id: dict[int, dict[str, Any]],
        timeout_dids: set[int],
        malformed_payloads: dict[int, bytes],
        malformed_snapshot_payloads: dict[tuple[int, int], bytes],
        dtc_statuses: dict[int, int],
        dtc_snapshots: dict[int, list[dict[str, Any]]],
        dtc_extended_data: dict[int, dict[int, bytes]],
        status_availability_mask: int,
    ) -> None:
        self._stack = stack
        self._dids_by_id = dids_by_id
        self._timeout_dids = timeout_dids
        self._malformed_payloads = malformed_payloads
        self._malformed_snapshot_payloads = malformed_snapshot_payloads
        self._dtc_statuses = dtc_statuses.copy()
        self._dtc_snapshots = {code: records.copy() for code, records in dtc_snapshots.items()}
        self._dtc_snapshot_record_numbers = {
            code: {int(item["record_number"]) for item in records}
            for code, records in dtc_snapshots.items()
        }
        self._dtc_extended_data = {
            code: records.copy() for code, records in dtc_extended_data.items()
        }
        self._persistent_dtc_statuses = self._dtc_statuses.copy()
        self._persistent_dtc_snapshots = {
            code: records.copy() for code, records in self._dtc_snapshots.items()
        }
        self._persistent_dtc_extended_data = {
            code: records.copy() for code, records in self._dtc_extended_data.items()
        }
        self._status_availability_mask = status_availability_mask
        self._stop = threading.Event()
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self._thread = threading.Thread(target=self._run, name="workbench-uds-responder")

    def start(self) -> None:
        self._stack.start()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self._stack.stop()

    def _run(self) -> None:
        while not self._stop.is_set():
            payload = self._stack.recv(block=True, timeout=0.05)
            if payload is None:
                continue
            request = bytes(payload)
            reset_after_response = False
            service_id = request[0] if request else -1
            did = int.from_bytes(request[1:3], "big") if service_id == 0x22 and len(request) >= 3 else -1
            request_evidence = {
                "service_id": service_id,
                "service_id_hex": f"0x{service_id:02X}" if service_id >= 0 else "",
                "payload_hex": request.hex().upper(),
            }
            if did >= 0:
                request_evidence["did"] = did
            self.requests.append(request_evidence)
            if service_id == 0x22 and len(request) >= 3:
                if did in self._timeout_dids:
                    continue
                if did in self._malformed_payloads:
                    response = self._malformed_payloads[did]
                elif did in self._dids_by_id:
                    response = _positive_response_payload(self._dids_by_id[did])
                else:
                    response = bytes([0x7F, 0x22, 0x31])
            elif service_id == 0x19 and len(request) == 3 and request[1] == 0x02:
                status_mask = request[2]
                response_data = bytearray([0x59, 0x02, self._status_availability_mask])
                for code, status in sorted(self._dtc_statuses.items()):
                    if status & status_mask:
                        response_data.extend(code.to_bytes(3, "big"))
                        response_data.append(status)
                response = bytes(response_data)
            elif service_id == 0x19 and len(request) == 6 and request[1] == 0x04:
                code = int.from_bytes(request[2:5], "big")
                record_number = request[5]
                if (code, record_number) in self._malformed_snapshot_payloads:
                    response = self._malformed_snapshot_payloads[(code, record_number)]
                elif (
                    code not in self._dtc_statuses
                    or record_number not in self._dtc_snapshot_record_numbers.get(code, set())
                ):
                    response = bytes([0x7F, 0x19, 0x31])
                else:
                    response_data = bytearray([0x59, 0x04])
                    response_data.extend(code.to_bytes(3, "big"))
                    response_data.append(self._dtc_statuses.get(code, 0))
                    records = [
                        item
                        for item in self._dtc_snapshots.get(code, [])
                        if int(item["record_number"]) == record_number
                    ]
                    if records:
                        response_data.extend([record_number, len(records)])
                        for item in records:
                            response_data.extend(int(item["did"]).to_bytes(2, "big"))
                            response_data.extend(bytes(item["data"]))
                    response = bytes(response_data)
            elif service_id == 0x19 and len(request) == 6 and request[1] == 0x06:
                code = int.from_bytes(request[2:5], "big")
                record_number = request[5]
                record = self._dtc_extended_data.get(code, {}).get(record_number)
                if code not in self._dtc_statuses or record is None:
                    response = bytes([0x7F, 0x19, 0x31])
                else:
                    response = (
                        bytes([0x59, 0x06])
                        + code.to_bytes(3, "big")
                        + bytes([self._dtc_statuses[code], record_number])
                        + record
                    )
            elif service_id == 0x14 and len(request) == 4:
                group = int.from_bytes(request[1:4], "big")
                if group == 0xFFFFFF:
                    self._dtc_statuses = {code: 0 for code in self._dtc_statuses}
                    self._dtc_snapshots = {code: [] for code in self._dtc_snapshots}
                    self._dtc_extended_data = {code: {} for code in self._dtc_extended_data}
                    self._persistent_dtc_statuses = self._dtc_statuses.copy()
                    self._persistent_dtc_snapshots = {
                        code: records.copy() for code, records in self._dtc_snapshots.items()
                    }
                    self._persistent_dtc_extended_data = {
                        code: records.copy() for code, records in self._dtc_extended_data.items()
                    }
                elif group in self._dtc_statuses:
                    self._dtc_statuses[group] = 0
                    self._dtc_snapshots[group] = []
                    self._dtc_extended_data[group] = {}
                    self._persistent_dtc_statuses[group] = 0
                    self._persistent_dtc_snapshots[group] = []
                    self._persistent_dtc_extended_data[group] = {}
                response = bytes([0x54])
            elif service_id == 0x11 and request == bytes([0x11, 0x01]):
                response = bytes([0x51, 0x01])
                reset_after_response = True
            else:
                response = bytes([0x7F, request[0] if request else 0x00, 0x11])
            self._stack.send(response)
            if reset_after_response:
                self._dtc_statuses = self._persistent_dtc_statuses.copy()
                self._dtc_snapshots = {
                    code: records.copy()
                    for code, records in self._persistent_dtc_snapshots.items()
                }
                self._dtc_extended_data = {
                    code: records.copy()
                    for code, records in self._persistent_dtc_extended_data.items()
                }
            response_evidence = {
                "service_id": response[0],
                "service_id_hex": f"0x{response[0]:02X}",
                "payload_hex": response.hex().upper(),
            }
            if did >= 0:
                response_evidence["did"] = did
            self.responses.append(response_evidence)


def _scenario_result(
    name: str,
    status: str,
    expected: str,
    observed: str,
    **evidence: Any,
) -> dict[str, Any]:
    return {
        "scenario": name,
        "status": status,
        "expected": expected,
        "observed": observed,
        "evidence": evidence,
    }


def _scenario_finding(code: str, message: str, intent: Path, scenario: str, severity: str = "ERROR") -> dict[str, Any]:
    return Finding(
        code=code,
        severity=severity,
        message=message,
        source_artifact=str(intent),
        kind="uds-scenario",
        location=scenario,
    ).to_dict()


def _run_scenario(client: Any, scenario: dict[str, Any], dids_by_id: dict[int, dict[str, Any]], intent_path: Path) -> dict[str, Any]:
    service = str(scenario["service"])
    if service == "ReadDTCInformation":
        if scenario.get("subfunction") == "reportDTCSnapshotRecordByDTCNumber":
            return _run_read_snapshot_scenario(client, scenario, intent_path)
        if scenario.get("subfunction") == "reportDTCExtendedDataRecordByDTCNumber":
            return _run_read_extended_data_scenario(client, scenario, intent_path)
        return _run_read_dtc_scenario(client, scenario, intent_path)
    if service == "ClearDiagnosticInformation":
        return _run_clear_dtc_scenario(client, scenario, intent_path)
    if service == "ECUReset":
        return _run_ecu_reset_scenario(client, scenario, intent_path)
    did = int(scenario["did"])
    name = str(scenario["name"])
    expected = str(scenario.get("expected", "positive"))
    request_hex = _request_payload(did).hex().upper()
    started = time.perf_counter()
    try:
        response = client.read_data_by_identifier(did)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        class_name = type(exc).__name__
        response_obj = getattr(exc, "response", None)
        response_hex = ""
        if response_obj is not None and getattr(response_obj, "original_payload", None) is not None:
            response_hex = response_obj.original_payload.hex().upper()
        if class_name == "NegativeResponseException":
            code_name = str(getattr(response_obj, "code_name", ""))
            passed = expected == "negative_response" and code_name.casefold() == str(scenario.get("nrc", "")).casefold()
            return _scenario_result(
                name,
                "passed" if passed else "failed",
                f"NRC {scenario.get('nrc', '')}",
                code_name,
                did=did,
                did_hex=f"0x{did:04X}",
                request_payload_hex=request_hex,
                response_payload_hex=response_hex,
                duration_ms=duration_ms,
                findings=[] if passed else [_scenario_finding("UDS-NEGATIVE-RESPONSE", str(exc), intent_path, name)],
            )
        if class_name == "TimeoutException":
            passed = expected == "timeout"
            return _scenario_result(
                name,
                "passed" if passed else "failed",
                "no positive or negative response before timeout",
                "timeout",
                did=did,
                did_hex=f"0x{did:04X}",
                request_payload_hex=request_hex,
                response_payload_hex="",
                duration_ms=duration_ms,
                findings=[] if passed else [_scenario_finding("UDS-RESPONSE-TIMEOUT", str(exc), intent_path, name)],
            )
        if expected == "malformed_payload":
            return _scenario_result(
                name,
                "passed",
                "malformed positive response rejected by client decoder",
                class_name,
                did=did,
                did_hex=f"0x{did:04X}",
                request_payload_hex=request_hex,
                response_payload_hex=response_hex,
                duration_ms=duration_ms,
                findings=[
                    _scenario_finding(
                        "UDS-MALFORMED-PAYLOAD",
                        f"DID 0x{did:04X} malformed response rejected as {class_name}: {exc}",
                        intent_path,
                        name,
                    )
                ],
            )
        return _scenario_result(
            name,
            "failed",
            expected,
            class_name,
            did=did,
            did_hex=f"0x{did:04X}",
            request_payload_hex=request_hex,
            response_payload_hex=response_hex,
            duration_ms=duration_ms,
            findings=[_scenario_finding("UDS-DID-DECODE-ERROR", str(exc), intent_path, name)],
        )

    duration_ms = round((time.perf_counter() - started) * 1000)
    values = getattr(response.service_data, "values", {})
    value = values.get(did)
    expected_value = dids_by_id.get(did, {}).get("value")
    response_hex = response.original_payload.hex().upper()
    if expected == "malformed_payload":
        return _scenario_result(
            name,
            "failed",
            "malformed positive response rejected by client decoder",
            "decoded unexpectedly",
            did=did,
            did_hex=f"0x{did:04X}",
            request_payload_hex=request_hex,
            response_payload_hex=response_hex,
            decoded_value=value,
            duration_ms=duration_ms,
            findings=[
                _scenario_finding(
                    "UDS-MALFORMED-PAYLOAD",
                    f"DID 0x{did:04X} malformed response decoded unexpectedly",
                    intent_path,
                    name,
                )
            ],
        )
    passed = expected == "positive" and value == expected_value
    return _scenario_result(
        name,
        "passed" if passed else "failed",
        f"positive response for DID 0x{did:04X}",
        "decoded" if passed else "mismatched positive response",
        did=did,
        did_hex=f"0x{did:04X}",
        request_payload_hex=request_hex,
        response_payload_hex=response_hex,
        decoded_value=value,
        expected_value=expected_value,
        duration_ms=duration_ms,
        findings=[] if passed else [
            _scenario_finding(
                "UDS-POSITIVE-RESPONSE-MISMATCH",
                f"DID 0x{did:04X} decoded {value!r}, expected {expected_value!r}",
                intent_path,
                name,
            )
        ],
    )


def _run_read_dtc_scenario(client: Any, scenario: dict[str, Any], intent_path: Path) -> dict[str, Any]:
    name = str(scenario["name"])
    status_mask = int(scenario["status_mask"])
    expected_records = sorted(
        (int(item["code"]), int(item["status"]))
        for item in scenario["expected_dtc_records"]
    )
    request_hex = bytes([0x19, 0x02, status_mask]).hex().upper()
    started = time.perf_counter()
    try:
        response = client.get_dtc_by_status_mask(status_mask)
        actual_records = sorted(
            (int(dtc.id), int(dtc.status.get_byte_as_int()))
            for dtc in response.service_data.dtcs
        )
        response_hex = response.original_payload.hex().upper()
    except Exception as exc:
        return _scenario_result(
            name,
            "failed",
            f"DTC records {[(f'0x{code:06X}', f'0x{status:02X}') for code, status in expected_records]}",
            type(exc).__name__,
            service="ReadDTCInformation",
            status_mask=status_mask,
            status_mask_hex=f"0x{status_mask:02X}",
            request_payload_hex=request_hex,
            response_payload_hex="",
            duration_ms=round((time.perf_counter() - started) * 1000),
            findings=[_scenario_finding("UDS-DTC-READ-ERROR", str(exc), intent_path, name)],
        )
    passed = actual_records == expected_records
    expected_evidence = [
        {"code": code, "code_hex": f"0x{code:06X}", "status": status, "status_hex": f"0x{status:02X}"}
        for code, status in expected_records
    ]
    actual_evidence = [
        {"code": code, "code_hex": f"0x{code:06X}", "status": status, "status_hex": f"0x{status:02X}"}
        for code, status in actual_records
    ]
    return _scenario_result(
        name,
        "passed" if passed else "failed",
        f"DTC records {[(item['code_hex'], item['status_hex']) for item in expected_evidence]}",
        f"DTC records {[(item['code_hex'], item['status_hex']) for item in actual_evidence]}",
        service="ReadDTCInformation",
        status_mask=status_mask,
        status_mask_hex=f"0x{status_mask:02X}",
        expected_dtc_records=expected_evidence,
        actual_dtc_records=actual_evidence,
        request_payload_hex=request_hex,
        response_payload_hex=response_hex,
        duration_ms=round((time.perf_counter() - started) * 1000),
        findings=[] if passed else [
            _scenario_finding(
                "UDS-DTC-LIST-MISMATCH",
                f"Observed DTC records {actual_records}, expected {expected_records}",
                intent_path,
                name,
            )
        ],
    )


def _run_clear_dtc_scenario(client: Any, scenario: dict[str, Any], intent_path: Path) -> dict[str, Any]:
    name = str(scenario["name"])
    group = int(scenario["group"])
    request_hex = bytes([0x14]) + group.to_bytes(3, "big")
    started = time.perf_counter()
    try:
        response = client.clear_dtc(group)
        response_hex = response.original_payload.hex().upper()
    except Exception as exc:
        return _scenario_result(
            name,
            "failed",
            f"clear group 0x{group:06X}",
            type(exc).__name__,
            service="ClearDiagnosticInformation",
            group=group,
            group_hex=f"0x{group:06X}",
            request_payload_hex=request_hex.hex().upper(),
            response_payload_hex="",
            duration_ms=round((time.perf_counter() - started) * 1000),
            findings=[_scenario_finding("UDS-DTC-CLEAR-ERROR", str(exc), intent_path, name)],
        )
    return _scenario_result(
        name,
        "passed",
        f"clear group 0x{group:06X}",
        "positive response",
        service="ClearDiagnosticInformation",
        group=group,
        group_hex=f"0x{group:06X}",
        request_payload_hex=request_hex.hex().upper(),
        response_payload_hex=response_hex,
        duration_ms=round((time.perf_counter() - started) * 1000),
        findings=[],
    )


def _run_ecu_reset_scenario(client: Any, scenario: dict[str, Any], intent_path: Path) -> dict[str, Any]:
    name = str(scenario["name"])
    request = bytes([0x11, 0x01])
    started = time.perf_counter()
    try:
        response = client.ecu_reset(0x01)
        response_hex = response.original_payload.hex().upper()
    except Exception as exc:
        return _scenario_result(
            name,
            "failed",
            "hardReset positive response",
            type(exc).__name__,
            service="ECUReset",
            reset_type="hardReset",
            reset_type_value=1,
            request_payload_hex=request.hex().upper(),
            response_payload_hex="",
            duration_ms=round((time.perf_counter() - started) * 1000),
            findings=[_scenario_finding("UDS-ECU-RESET-ERROR", str(exc), intent_path, name)],
        )
    passed = response_hex == "5101"
    return _scenario_result(
        name,
        "passed" if passed else "failed",
        "hardReset positive response 0x5101",
        response_hex,
        service="ECUReset",
        reset_type="hardReset",
        reset_type_value=1,
        request_payload_hex=request.hex().upper(),
        response_payload_hex=response_hex,
        duration_ms=round((time.perf_counter() - started) * 1000),
        findings=[] if passed else [
            _scenario_finding(
                "UDS-ECU-RESET-MISMATCH",
                f"Observed ECUReset response {response_hex}, expected 5101",
                intent_path,
                name,
            )
        ],
    )


def _run_read_snapshot_scenario(
    client: Any,
    scenario: dict[str, Any],
    intent_path: Path,
) -> dict[str, Any]:
    name = str(scenario["name"])
    code = int(scenario["dtc"])
    record_number = int(scenario["record_number"])
    expected = str(scenario.get("expected", "positive"))
    expected_status = int(scenario.get("expected_dtc_status", 0))
    expected_records = sorted(
        (record_number, int(item["did"]), item["value"])
        for item in scenario.get("expected_snapshot_records", [])
    )
    request = bytes([0x19, 0x04]) + code.to_bytes(3, "big") + bytes([record_number])
    started = time.perf_counter()
    try:
        response = client.get_dtc_snapshot_by_dtc_number(code, record_number)
        dtc = response.service_data.dtcs[0]
        actual_status = int(dtc.status.get_byte_as_int())
        actual_records = []
        actual_evidence = []
        for snapshot in dtc.snapshots:
            value = snapshot.data
            if isinstance(value, tuple) and len(value) == 1:
                value = value[0]
            actual_records.append((int(snapshot.record_number), int(snapshot.did), value))
            actual_evidence.append({
                "record_number": int(snapshot.record_number),
                "did": int(snapshot.did),
                "did_hex": f"0x{int(snapshot.did):04X}",
                "value": value,
                "payload_hex": bytes(snapshot.raw_data).hex().upper(),
            })
        actual_records.sort()
        actual_evidence.sort(key=lambda item: (item["record_number"], item["did"]))
        response_hex = response.original_payload.hex().upper()
    except Exception as exc:
        response_obj = getattr(exc, "response", None)
        response_hex = ""
        if response_obj is not None and getattr(response_obj, "original_payload", None) is not None:
            response_hex = response_obj.original_payload.hex().upper()
        class_name = type(exc).__name__
        if class_name == "NegativeResponseException":
            code_name = str(getattr(response_obj, "code_name", ""))
            passed = (
                expected == "negative_response"
                and code_name.casefold() == str(scenario.get("nrc", "")).casefold()
            )
            return _scenario_result(
                name,
                "passed" if passed else "failed",
                f"NRC {scenario.get('nrc', '')}",
                code_name,
                service="ReadDTCInformation",
                subfunction="reportDTCSnapshotRecordByDTCNumber",
                dtc=code,
                dtc_hex=f"0x{code:06X}",
                record_number=record_number,
                request_payload_hex=request.hex().upper(),
                response_payload_hex=response_hex,
                duration_ms=round((time.perf_counter() - started) * 1000),
                findings=[] if passed else [
                    _scenario_finding("UDS-DTC-SNAPSHOT-NEGATIVE-RESPONSE", str(exc), intent_path, name)
                ],
            )
        if expected == "malformed_payload":
            passed = class_name == "InvalidResponseException"
            return _scenario_result(
                name,
                "passed" if passed else "failed",
                "malformed snapshot response rejected by client decoder",
                class_name,
                service="ReadDTCInformation",
                subfunction="reportDTCSnapshotRecordByDTCNumber",
                dtc=code,
                dtc_hex=f"0x{code:06X}",
                record_number=record_number,
                request_payload_hex=request.hex().upper(),
                response_payload_hex=response_hex,
                duration_ms=round((time.perf_counter() - started) * 1000),
                findings=[
                    _scenario_finding(
                        "UDS-DTC-SNAPSHOT-MALFORMED",
                        f"Snapshot response rejected as {class_name}: {exc}",
                        intent_path,
                        name,
                    )
                ],
            )
        return _scenario_result(
            name,
            "failed",
            f"snapshot record 0x{record_number:02X} for DTC 0x{code:06X}",
            type(exc).__name__,
            service="ReadDTCInformation",
            subfunction="reportDTCSnapshotRecordByDTCNumber",
            dtc=code,
            dtc_hex=f"0x{code:06X}",
            record_number=record_number,
            request_payload_hex=request.hex().upper(),
            response_payload_hex=response_hex,
            duration_ms=round((time.perf_counter() - started) * 1000),
            findings=[_scenario_finding("UDS-DTC-SNAPSHOT-READ-ERROR", str(exc), intent_path, name)],
        )
    passed = expected == "positive" and actual_status == expected_status and actual_records == expected_records
    return _scenario_result(
        name,
        "passed" if passed else "failed",
        f"DTC 0x{code:06X} status 0x{expected_status:02X} snapshot {expected_records}",
        f"DTC 0x{code:06X} status 0x{actual_status:02X} snapshot {actual_records}",
        service="ReadDTCInformation",
        subfunction="reportDTCSnapshotRecordByDTCNumber",
        dtc=code,
        dtc_hex=f"0x{code:06X}",
        expected_dtc_status=expected_status,
        expected_dtc_status_hex=f"0x{expected_status:02X}",
        actual_dtc_status=actual_status,
        actual_dtc_status_hex=f"0x{actual_status:02X}",
        record_number=record_number,
        expected_snapshot_records=scenario.get("expected_snapshot_records", []),
        actual_snapshot_records=actual_evidence,
        request_payload_hex=request.hex().upper(),
        response_payload_hex=response_hex,
        duration_ms=round((time.perf_counter() - started) * 1000),
        findings=[] if passed else [
            _scenario_finding(
                "UDS-DTC-SNAPSHOT-MISMATCH",
                f"Observed status/snapshot {(actual_status, actual_records)}, expected {(expected_status, expected_records)}",
                intent_path,
                name,
            )
        ],
    )


def _run_read_extended_data_scenario(
    client: Any,
    scenario: dict[str, Any],
    intent_path: Path,
) -> dict[str, Any]:
    name = str(scenario["name"])
    code = int(scenario["dtc"])
    record_number = int(scenario["record_number"])
    expected = str(scenario.get("expected", "positive"))
    expected_status = int(scenario.get("expected_dtc_status", 0))
    expected_value = int(scenario.get("expected_extended_data_value", 0))
    request = bytes([0x19, 0x06]) + code.to_bytes(3, "big") + bytes([record_number])
    started = time.perf_counter()
    try:
        response = client.get_dtc_extended_data_by_dtc_number(
            code,
            record_number=record_number,
            data_size=1,
        )
        dtc = response.service_data.dtcs[0]
        actual_status = int(dtc.status.get_byte_as_int())
        record = dtc.extended_data[0]
        actual_record_number = int(record.record_number)
        raw_data = bytes(record.raw_data)
        actual_value = raw_data[0]
        response_hex = response.original_payload.hex().upper()
    except Exception as exc:
        response_obj = getattr(exc, "response", None)
        response_hex = ""
        if response_obj is not None and getattr(response_obj, "original_payload", None) is not None:
            response_hex = response_obj.original_payload.hex().upper()
        class_name = type(exc).__name__
        if class_name == "NegativeResponseException":
            code_name = str(getattr(response_obj, "code_name", ""))
            passed = (
                expected == "negative_response"
                and code_name.casefold() == str(scenario.get("nrc", "")).casefold()
            )
            return _scenario_result(
                name,
                "passed" if passed else "failed",
                f"NRC {scenario.get('nrc', '')}",
                code_name,
                service="ReadDTCInformation",
                subfunction="reportDTCExtendedDataRecordByDTCNumber",
                dtc=code,
                dtc_hex=f"0x{code:06X}",
                record_number=record_number,
                request_payload_hex=request.hex().upper(),
                response_payload_hex=response_hex,
                duration_ms=round((time.perf_counter() - started) * 1000),
                findings=[] if passed else [
                    _scenario_finding("UDS-DTC-EXTENDED-DATA-NRC", str(exc), intent_path, name)
                ],
            )
        return _scenario_result(
            name,
            "failed",
            expected,
            class_name,
            service="ReadDTCInformation",
            subfunction="reportDTCExtendedDataRecordByDTCNumber",
            dtc=code,
            dtc_hex=f"0x{code:06X}",
            record_number=record_number,
            request_payload_hex=request.hex().upper(),
            response_payload_hex=response_hex,
            duration_ms=round((time.perf_counter() - started) * 1000),
            findings=[_scenario_finding("UDS-DTC-EXTENDED-DATA-READ-ERROR", str(exc), intent_path, name)],
        )
    passed = (
        expected == "positive"
        and actual_status == expected_status
        and actual_record_number == record_number
        and actual_value == expected_value
    )
    return _scenario_result(
        name,
        "passed" if passed else "failed",
        f"DTC 0x{code:06X} record 0x{record_number:02X} value {expected_value}",
        f"DTC 0x{code:06X} record 0x{actual_record_number:02X} value {actual_value}",
        service="ReadDTCInformation",
        subfunction="reportDTCExtendedDataRecordByDTCNumber",
        dtc=code,
        dtc_hex=f"0x{code:06X}",
        record_number=record_number,
        expected_dtc_status=expected_status,
        actual_dtc_status=actual_status,
        expected_extended_data_value=expected_value,
        actual_extended_data_value=actual_value,
        extended_data_payload_hex=raw_data.hex().upper(),
        request_payload_hex=request.hex().upper(),
        response_payload_hex=response_hex,
        duration_ms=round((time.perf_counter() - started) * 1000),
        findings=[] if passed else [
            _scenario_finding(
                "UDS-DTC-EXTENDED-DATA-MISMATCH",
                f"Observed {(actual_status, actual_record_number, actual_value)}, expected {(expected_status, record_number, expected_value)}",
                intent_path,
                name,
            )
        ],
    )


def render_uds_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# UDS/ISO-TP Diagnostic Lab Report",
        "",
        f"- Run ID: `{result['run_id']}`",
        f"- ECU: `{result['ecu']}`",
        f"- Backend: `{result['backend']}`",
        f"- Status: **{result['status']}**",
        f"- Scenarios: {result['passed_count']}/{result['scenario_count']} passed",
        f"- Request CAN ID: `{result['transport']['request_id_hex']}`",
        f"- Response CAN ID: `{result['transport']['response_id_hex']}`",
        "",
        "| Scenario | Result | Identifier | Expected | Observed |",
        "|---|---|---:|---|---|",
    ]
    for item in result["scenarios"]:
        evidence = item["evidence"]
        identifier = evidence.get("did_hex") or evidence.get("status_mask_hex") or evidence.get("group_hex") or "-"
        lines.append(
            f"| `{item['scenario']}` | {item['status']} | `{identifier}` | {item['expected']} | {item['observed']} |"
        )
    if result["findings"]:
        lines.extend(["", "## Findings", ""])
        for finding in result["findings"]:
            lines.append(f"- `{finding['code']}` {finding['message']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This lab proves a deterministic UDS client/responder flow over user-space ISO-TP and the selected python-can backend. It is not a DCM, DEM, security access, flash programming, production timing, or hardware conformance proof.",
        "",
    ])
    return "\n".join(lines)


def _blocked_result(
    intent: Path,
    dtc_path: Path | None,
    payload: dict[str, Any],
    config: BusConfig,
    transport: dict[str, Any],
    probe: dict[str, Any],
    timestamp: datetime,
    isolation: dict[str, Any],
) -> dict[str, Any]:
    request_id = int(transport["request_id"])
    response_id = int(transport["response_id"])
    return {
        "artifact_type": "uds-isotp-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "ecu": payload["ecu"],
        "backend": f"python-can {config.interface}",
        "applicability_profile": build_runtime_applicability_profile(
            variant=payload["ecu"],
            software_version="uds-lab-0.1",
            inputs=[intent, *([dtc_path] if dtc_path is not None else [])],
            backend=f"python-can {config.interface}",
        ),
        "status": "blocked",
        "reason": probe.get("reason", "backend_unavailable"),
        "scenario_count": len(payload["scenarios"]),
        "passed_count": 0,
        "duration_ms": 0,
        "artifacts": [str(intent)],
        "bus_config": {
            "interface": config.interface,
            "channel": config.channel,
            "receive_own_messages": config.receive_own_messages,
            "fd": config.fd,
        },
        "transport": {
            "addressing": transport["addressing"],
            "request_id": request_id,
            "request_id_hex": f"0x{request_id:03X}",
            "response_id": response_id,
            "response_id_hex": f"0x{response_id:03X}",
            "tx_data_length": transport["tx_data_length"],
        },
        "isotp_params": {"tx_data_length": int(transport["tx_data_length"])},
        "scenarios": [],
        "responder_observed_requests": [],
        "responder_sent_responses": [],
        "findings": [],
        "backend_probe": probe,
        "isolation": isolation,
    }


def run_uds_lab(intent: Path, config: BusConfig, output: Path) -> dict[str, Any]:
    can, isotp, ascii_codec, client_cls, connection_cls = _diag_libs()
    payload = load_uds_intent(intent)
    transport = payload["transport"]
    dtc_path = intent.parent / payload["dtc_intent"] if payload.get("dtc_intent") else None
    dtc_payload = load_dtc_intent(dtc_path) if dtc_path is not None else None
    timestamp = datetime.now(timezone.utc)

    if config.interface == "virtual" and config.channel == "workbench":
        config = BusConfig(config.interface, f"workbench-uds-{uuid.uuid4()}", config.receive_own_messages, config.fd)

    request_id = int(transport["request_id"])
    response_id = int(transport["response_id"])
    client_filters = exact_can_filters(response_id)
    server_filters = exact_can_filters(request_id)
    isolation = {
        "client": bus_isolation_evidence(config, client_filters),
        "server": bus_isolation_evidence(config, server_filters),
    }

    probe = probe_can_backend(config, output / "probe")
    if probe["status"] != "available":
        result = _blocked_result(
            intent, dtc_path, payload, config, transport, probe, timestamp, isolation
        )
        output.mkdir(parents=True, exist_ok=True)
        (output / "uds-lab-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "uds-lab-report.md").write_text(render_uds_markdown(result), encoding="utf-8")
        return result

    dids_by_id = {int(did["id"]): did for did in payload["dids"]}
    timeout_dids = {
        int(scenario["did"])
        for scenario in payload["scenarios"]
        if scenario.get("expected") == "timeout"
    }
    malformed_payloads = {
        int(scenario["did"]): bytes.fromhex(str(scenario["response_payload_hex"]))
        for scenario in payload["scenarios"]
        if scenario.get("expected") == "malformed_payload"
        and scenario.get("service") == "ReadDataByIdentifier"
    }
    malformed_snapshot_payloads = {
        (int(scenario["dtc"]), int(scenario["record_number"])): bytes.fromhex(
            str(scenario["response_payload_hex"])
        )
        for scenario in payload["scenarios"]
        if scenario.get("expected") == "malformed_payload"
        and scenario.get("subfunction") == "reportDTCSnapshotRecordByDTCNumber"
    }
    data_identifiers = {
        int(did["id"]): _client_codec(did, ascii_codec)
        for did in payload["dids"]
    }
    for scenario in payload["scenarios"]:
        if "did" in scenario:
            data_identifiers.setdefault(int(scenario["did"]), "B")
    dtc_statuses = {
        int(item["code"]): int(item["uds_initial_status"])
        for item in (dtc_payload or {}).get("dtcs", [])
    }
    dtc_snapshots = {
        int(item["code"]): [
            {
                "record_number": int(item["snapshot"]["record_number"]),
                "did": int(snapshot_did["did"]),
                "data": bytes([int(snapshot_did["value"])]),
            }
            for snapshot_did in item["snapshot"]["dids"]
        ]
        for item in (dtc_payload or {}).get("dtcs", [])
    }
    dtc_extended_data = {
        int(item["code"]): {
            int(record["record_number"]): bytes([int(record["uds_initial_value"])])
            for record in item["extended_data"]["records"]
        }
        for item in (dtc_payload or {}).get("dtcs", [])
    }
    status_availability_mask = int((dtc_payload or {}).get("status_availability_mask", 0xFF))

    client_bus = open_bus(config, client_filters)
    server_bus = open_bus(config, server_filters)
    client_notifier = can.Notifier(client_bus, [])
    server_notifier = can.Notifier(server_bus, [])
    isotp_params = {"tx_data_length": int(transport["tx_data_length"])}
    client_stack = isotp.NotifierBasedCanStack(
        client_bus,
        client_notifier,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=request_id, rxid=response_id),
        params=isotp_params,
    )
    server_stack = isotp.NotifierBasedCanStack(
        server_bus,
        server_notifier,
        address=isotp.Address(isotp.AddressingMode.Normal_11bits, txid=response_id, rxid=request_id),
        params=isotp_params,
    )
    responder = _UdsResponder(
        server_stack,
        dids_by_id,
        timeout_dids,
        malformed_payloads,
        malformed_snapshot_payloads,
        dtc_statuses,
        dtc_snapshots,
        dtc_extended_data,
        status_availability_mask,
    )
    client_logger = logging.getLogger("UdsClient[workbench-uds-lab]")
    previous_level = client_logger.level
    started = time.perf_counter()
    scenarios: list[dict[str, Any]] = []
    try:
        client_logger.setLevel(logging.CRITICAL)
        responder.start()
        connection = connection_cls(client_stack)
        client_config = {
            "logger_name": "workbench-uds-lab",
            "data_identifiers": data_identifiers,
            "request_timeout": 0.5,
            "p2_timeout": 0.2,
            "p2_star_timeout": 0.5,
            "exception_on_negative_response": True,
            "exception_on_invalid_response": True,
            "exception_on_unexpected_response": True,
            "tolerate_zero_padding": True,
        }
        with client_cls(connection, config=client_config) as client:
            scenarios = [
                _run_scenario(client, scenario, dids_by_id, intent)
                for scenario in payload["scenarios"]
            ]
    finally:
        client_logger.setLevel(previous_level)
        responder.stop()
        client_notifier.stop()
        server_notifier.stop()
        client_bus.shutdown()
        server_bus.shutdown()

    findings = [
        finding
        for scenario in scenarios
        for finding in scenario["evidence"].get("findings", [])
    ]
    passed_count = sum(item["status"] == "passed" for item in scenarios)
    result = {
        "artifact_type": "uds-isotp-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "ecu": payload["ecu"],
        "backend": f"python-can {config.interface}",
        "applicability_profile": build_runtime_applicability_profile(
            variant=payload["ecu"],
            software_version="uds-lab-0.1",
            inputs=[intent, *([dtc_path] if dtc_path is not None else [])],
            backend=f"python-can {config.interface}",
        ),
        "status": "passed" if passed_count == len(scenarios) else "failed",
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "artifacts": [str(intent), *([str(dtc_path)] if dtc_path is not None else [])],
        "bus_config": {
            "interface": config.interface,
            "channel": config.channel,
            "receive_own_messages": config.receive_own_messages,
            "fd": config.fd,
        },
        "transport": {
            "addressing": transport["addressing"],
            "request_id": request_id,
            "request_id_hex": f"0x{request_id:03X}",
            "response_id": response_id,
            "response_id_hex": f"0x{response_id:03X}",
            "tx_data_length": transport["tx_data_length"],
        },
        "isotp_params": isotp_params,
        "scenarios": scenarios,
        "responder_observed_requests": responder.requests,
        "responder_sent_responses": responder.responses,
        "findings": findings,
        "backend_probe": probe,
        "isolation": isolation,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "uds-lab-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "uds-lab-report.md").write_text(render_uds_markdown(result), encoding="utf-8")
    return result
