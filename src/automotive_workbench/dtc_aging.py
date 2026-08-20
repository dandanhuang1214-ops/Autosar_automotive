from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding
from automotive_workbench.dtc_intent import load_dtc_intent


@dataclass
class _CycleState:
    state: str = "absent"
    status: int = 0x50
    aging_counter: int = 0
    failure_count: int = 0
    confirmed_once: bool = False
    cycle_active: bool = False
    tested_this_cycle: bool = False
    failed_this_cycle: bool = False
    snapshot: list[dict[str, Any]] = field(default_factory=list)


def _capture_snapshot(state: _CycleState, definition: dict[str, Any]) -> None:
    if state.snapshot:
        return
    snapshot = definition["snapshot"]
    state.snapshot = [
        {
            "record_number": int(snapshot["record_number"]),
            "did": int(item["did"]),
            "did_hex": f"0x{int(item['did']):04X}",
            "value": int(item["value"]),
            "payload_hex": bytes([int(item["value"])]).hex().upper(),
        }
        for item in snapshot["dids"]
    ]


def _apply_cycle_event(state: _CycleState, event: str, definition: dict[str, Any]) -> None:
    if event == "operation_cycle_start":
        if state.cycle_active:
            raise ValueError("operation cycle is already active")
        state.cycle_active = True
        state.tested_this_cycle = False
        state.failed_this_cycle = False
        state.status = (state.status & ~0x02) | 0x40
        return
    if event == "operation_cycle_end":
        if not state.cycle_active:
            raise ValueError("operation cycle is not active")
        if state.tested_this_cycle and not state.failed_this_cycle and state.confirmed_once:
            state.status &= ~0x04
            state.aging_counter += 1
            if state.aging_counter >= int(definition["aging_threshold"]):
                state.status &= ~(0x08 | 0x20)
                state.state = "aged_out"
                state.snapshot = []
                state.confirmed_once = False
            else:
                state.state = "healed"
        elif state.failed_this_cycle:
            state.aging_counter = 0
        state.cycle_active = False
        return
    if event == "read_snapshot":
        return
    if not state.cycle_active:
        raise ValueError(f"{event} requires an active operation cycle")
    state.tested_this_cycle = True
    state.status &= ~(0x10 | 0x40)
    if event == "fault_present":
        state.failed_this_cycle = True
        state.failure_count += 1
        state.status |= 0x27
        if state.failure_count >= int(definition["failure_threshold"]):
            state.status |= 0x08
            state.state = "confirmed"
            state.confirmed_once = True
            _capture_snapshot(state, definition)
        else:
            state.state = "pending"
    else:
        state.failed_this_cycle = False
        state.failure_count = 0
        state.status &= ~(0x01 | 0x02)
        if state.confirmed_once:
            state.state = "healing" if state.state == "confirmed" else "healed"


def _snapshot_payloads(state: _CycleState, definition: dict[str, Any]) -> tuple[str, str]:
    code = int(definition["code"])
    record_number = int(definition["snapshot"]["record_number"])
    request = bytes([0x19, 0x04]) + code.to_bytes(3, "big") + bytes([record_number])
    response = bytearray([0x59, 0x04])
    response.extend(code.to_bytes(3, "big"))
    response.append(state.status)
    if state.snapshot:
        response.extend([record_number, len(state.snapshot)])
        for item in state.snapshot:
            response.extend(int(item["did"]).to_bytes(2, "big"))
            response.extend(bytes.fromhex(str(item["payload_hex"])))
    return request.hex().upper(), bytes(response).hex().upper()


def run_dtc_aging_lab(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {int(item["code"]): item for item in payload["dtcs"]}
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["cycle_experiments"]:
        definition = dtcs[int(experiment["dtc"])]
        state = _CycleState()
        for index, step in enumerate(experiment["steps"]):
            error = ""
            try:
                _apply_cycle_event(state, str(step["event"]), definition)
            except ValueError as exc:
                error = str(exc)
            request_hex = ""
            response_hex = ""
            if step["event"] == "read_snapshot":
                request_hex, response_hex = _snapshot_payloads(state, definition)
            passed = not error and all([
                state.state == step["expected_state"],
                state.status == step["expected_status"],
                state.aging_counter == step["expected_aging_counter"],
                bool(state.snapshot) == step["expected_snapshot_stored"],
                state.cycle_active == step["expected_cycle_active"],
            ])
            trace = {
                "experiment": experiment["name"],
                "step": index,
                "event": step["event"],
                "status": "passed" if passed else "failed",
                "dtc": definition["code"],
                "dtc_hex": f"0x{int(definition['code']):06X}",
                "expected_state": step["expected_state"],
                "observed_state": state.state,
                "expected_dtc_status_hex": f"0x{int(step['expected_status']):02X}",
                "observed_dtc_status": state.status,
                "observed_dtc_status_hex": f"0x{state.status:02X}",
                "expected_aging_counter": step["expected_aging_counter"],
                "observed_aging_counter": state.aging_counter,
                "expected_snapshot_stored": step["expected_snapshot_stored"],
                "snapshot_stored": bool(state.snapshot),
                "snapshot": state.snapshot.copy(),
                "expected_cycle_active": step["expected_cycle_active"],
                "cycle_active": state.cycle_active,
                "request_payload_hex": request_hex,
                "response_payload_hex": response_hex,
                "error": error,
            }
            traces.append(trace)
            if not passed:
                code = "DTC-CYCLE-SEQUENCE" if error else "DTC-CYCLE-MISMATCH"
                findings.append(Finding(
                    code=code,
                    severity="ERROR",
                    message=(
                        error or f"{experiment['name']} step {index} did not match expected cycle evidence"
                    ),
                    source_artifact=str(intent),
                    kind="dtc-operation-cycle",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "dtc-aging-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if not findings else "failed",
        "ecu": payload["ecu"],
        "experiment_count": len(payload["cycle_experiments"]),
        "step_count": len(traces),
        "passed_count": sum(item["status"] == "passed" for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-aging-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Operation Cycle and Aging Report",
        "",
        f"- Status: **{result['status']}**",
        f"- ECU: `{result['ecu']}`",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        "",
        "| Step | Event | State | Status | Aging | Snapshot | Cycle active |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for item in traces:
        lines.append(
            f"| {item['step']} | `{item['event']}` | {item['observed_state']} | "
            f"`{item['observed_dtc_status_hex']}` | {item['observed_aging_counter']} | "
            f"{item['snapshot_stored']} | {item['cycle_active']} |"
        )
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            lines.append(f"- `{finding['code']}` {finding['message']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This is a deterministic research model for explicit operation cycles, tested-pass aging and one confirmed-trigger snapshot. It is not a production Dem event memory, displacement, NVRAM or OBD implementation.",
        "",
    ])
    (output / "dtc-aging-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result
