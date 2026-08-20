from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding
from automotive_workbench.dtc_intent import load_dtc_intent


@dataclass
class _DtcState:
    state: str = "absent"
    status: int = 0
    failure_count: int = 0
    healing_count: int = 0
    confirmed_once: bool = False


def _apply_event(state: _DtcState, event: str, failure_threshold: int, healing_threshold: int) -> None:
    if event == "clear_dtc":
        state.state = "absent"
        state.status = 0
        state.failure_count = 0
        state.healing_count = 0
        state.confirmed_once = False
    elif event == "fault_present":
        state.failure_count += 1
        state.healing_count = 0
        if state.failure_count >= failure_threshold:
            state.state = "confirmed"
            state.status = 0x2D
            state.confirmed_once = True
        else:
            state.state = "pending"
            state.status = 0x25
    elif event == "fault_absent" and state.state != "absent":
        state.healing_count += 1
        state.failure_count = 0
        if state.healing_count >= healing_threshold:
            state.state = "healed"
            state.status = 0x28 if state.confirmed_once else 0x20
        else:
            state.state = "healing"
            state.status = 0x2C if state.confirmed_once else 0x24


def _read_payload(code: int, status: int, status_mask: int, availability_mask: int) -> tuple[str, str]:
    request = bytes([0x19, 0x02, status_mask])
    response = bytearray([0x59, 0x02, availability_mask])
    if status & status_mask:
        response.extend(code.to_bytes(3, "big"))
        response.append(status)
    return request.hex().upper(), bytes(response).hex().upper()


def run_dtc_lifecycle(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {item["code"]: item for item in payload["dtcs"]}
    availability_mask = int(payload.get("status_availability_mask", 0xFF))
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["experiments"]:
        definition = dtcs[experiment["dtc"]]
        state = _DtcState()
        for index, step in enumerate(experiment["steps"]):
            event = step["event"]
            _apply_event(
                state,
                event,
                int(definition["failure_threshold"]),
                int(definition["healing_threshold"]),
            )
            request_hex = ""
            response_hex = ""
            if event == "read_dtc":
                request_hex, response_hex = _read_payload(
                    int(definition["code"]), state.status, int(step["status_mask"]), availability_mask
                )
            elif event == "clear_dtc":
                request_hex, response_hex = "14FFFFFF", "54"
            passed = state.state == step["expected_state"] and state.status == step["expected_status"]
            trace = {
                "experiment": experiment["name"],
                "dtc": definition["code"],
                "dtc_hex": f"0x{definition['code']:06X}",
                "step": index,
                "event": event,
                "status": "passed" if passed else "failed",
                "expected_state": step["expected_state"],
                "observed_state": state.state,
                "expected_dtc_status": step["expected_status"],
                "expected_dtc_status_hex": f"0x{step['expected_status']:02X}",
                "observed_dtc_status": state.status,
                "observed_dtc_status_hex": f"0x{state.status:02X}",
                "request_payload_hex": request_hex,
                "response_payload_hex": response_hex,
            }
            traces.append(trace)
            if not passed:
                findings.append(Finding(
                    code="DTC-LIFECYCLE-MISMATCH",
                    severity="ERROR",
                    message=(
                        f"{experiment['name']} step {index}: observed {state.state}/0x{state.status:02X}, "
                        f"expected {step['expected_state']}/0x{step['expected_status']:02X}"
                    ),
                    source_artifact=str(intent),
                    kind="dtc-lifecycle",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "dtc-lifecycle-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if not findings else "failed",
        "ecu": payload["ecu"],
        "dtc_count": len(dtcs),
        "experiment_count": len(payload["experiments"]),
        "step_count": len(traces),
        "passed_count": sum(item["status"] == "passed" for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-lifecycle-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Lifecycle Lab Report",
        "",
        f"- Status: **{result['status']}**",
        f"- ECU: `{result['ecu']}`",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        "",
        "| Step | Event | Expected | Observed | UDS request | UDS response |",
        "|---:|---|---|---|---|---|",
    ]
    for item in traces:
        lines.append(
            f"| {item['step']} | `{item['event']}` | {item['expected_state']} / "
            f"`{item['expected_dtc_status_hex']}` | {item['observed_state']} / "
            f"`{item['observed_dtc_status_hex']}` | `{item['request_payload_hex'] or '-'}` | "
            f"`{item['response_payload_hex'] or '-'}` |"
        )
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            lines.append(f"- `{finding['code']}` {finding['message']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This is a deterministic research lifecycle with explicit debounce and healing thresholds. It is not a production DEM operation-cycle, aging, displacement, freeze-frame, or NVRAM implementation.",
        "",
    ])
    (output / "dtc-lifecycle-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result
