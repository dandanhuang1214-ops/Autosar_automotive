from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding
from automotive_workbench.dtc_aging import _CycleState, _apply_cycle_event
from automotive_workbench.dtc_intent import load_dtc_intent


def _cleared_state() -> _CycleState:
    return _CycleState(status=0, state="absent")


def _apply_reset_event(
    runtime: _CycleState,
    persistent: _CycleState,
    event: str,
    definition: dict[str, Any],
) -> tuple[_CycleState, _CycleState]:
    if event in {"operation_cycle_start", "operation_cycle_end", "fault_present"}:
        _apply_cycle_event(runtime, event, definition)
        return runtime, persistent
    if event == "flush":
        if runtime.cycle_active:
            raise ValueError("flush requires an inactive operation cycle")
        return runtime, copy.deepcopy(runtime)
    if event == "hard_reset":
        restored = copy.deepcopy(persistent)
        restored.cycle_active = False
        restored.tested_this_cycle = False
        restored.failed_this_cycle = False
        return restored, persistent
    if event == "clear_dtc":
        return _cleared_state(), _cleared_state()
    raise ValueError(f"unsupported reset event: {event}")


def run_dtc_reset_lab(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {int(item["code"]): item for item in payload["dtcs"]}
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["reset_experiments"]:
        definition = dtcs[int(experiment["dtc"])]
        runtime = _CycleState()
        persistent = _cleared_state()
        for index, step in enumerate(experiment["steps"]):
            error = ""
            try:
                runtime, persistent = _apply_reset_event(
                    runtime,
                    persistent,
                    str(step["event"]),
                    definition,
                )
            except ValueError as exc:
                error = str(exc)
            runtime_extended = runtime.confirmed_once
            persistent_extended = persistent.confirmed_once
            passed = not error and all([
                runtime.state == step["expected_runtime_state"],
                runtime.status == step["expected_runtime_status"],
                persistent.status == step["expected_persistent_status"],
                bool(runtime.snapshot) == step["expected_runtime_snapshot_stored"],
                bool(persistent.snapshot) == step["expected_persistent_snapshot_stored"],
                runtime_extended == step["expected_runtime_extended_data_stored"],
                persistent_extended == step["expected_persistent_extended_data_stored"],
            ])
            hard_reset = step["event"] == "hard_reset"
            trace = {
                "experiment": experiment["name"],
                "step": index,
                "event": step["event"],
                "status": "passed" if passed else "failed",
                "dtc": definition["code"],
                "dtc_hex": f"0x{int(definition['code']):06X}",
                "expected_runtime_state": step["expected_runtime_state"],
                "runtime_state": runtime.state,
                "expected_runtime_status_hex": f"0x{int(step['expected_runtime_status']):02X}",
                "runtime_status": runtime.status,
                "runtime_status_hex": f"0x{runtime.status:02X}",
                "expected_persistent_status_hex": f"0x{int(step['expected_persistent_status']):02X}",
                "persistent_status": persistent.status,
                "persistent_status_hex": f"0x{persistent.status:02X}",
                "runtime_snapshot_stored": bool(runtime.snapshot),
                "persistent_snapshot_stored": bool(persistent.snapshot),
                "runtime_extended_data_stored": runtime_extended,
                "persistent_extended_data_stored": persistent_extended,
                "cycle_active": runtime.cycle_active,
                "request_payload_hex": "1101" if hard_reset else "",
                "response_payload_hex": "5101" if hard_reset else "",
                "error": error,
            }
            traces.append(trace)
            if not passed:
                findings.append(Finding(
                    code="DTC-RESET-SEQUENCE" if error else "DTC-RESET-MISMATCH",
                    severity="ERROR",
                    message=error or f"{experiment['name']} step {index} did not match reset evidence",
                    source_artifact=str(intent),
                    kind="dtc-reset-persistence",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "dtc-reset-persistence-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if not findings else "failed",
        "ecu": payload["ecu"],
        "experiment_count": len(payload["reset_experiments"]),
        "step_count": len(traces),
        "passed_count": sum(item["status"] == "passed" for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-reset-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Reset and Persistence Report",
        "",
        f"- Status: **{result['status']}**",
        f"- ECU: `{result['ecu']}`",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        "",
        "| Step | Event | Runtime state | Runtime status | Persistent status | Runtime data | Persistent data |",
        "|---:|---|---|---|---|---|---|",
    ]
    for item in traces:
        lines.append(
            f"| {item['step']} | `{item['event']}` | {item['runtime_state']} | "
            f"`{item['runtime_status_hex']}` | `{item['persistent_status_hex']}` | "
            f"{item['runtime_snapshot_stored']}/{item['runtime_extended_data_stored']} | "
            f"{item['persistent_snapshot_stored']}/{item['persistent_extended_data_stored']} |"
        )
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            lines.append(f"- `{finding['code']}` {finding['message']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "The persistent mirror is in-process deterministic evidence. This is not AUTOSAR NvM, power-loss, flash, startup timing, or hardware reset proof.",
        "",
    ])
    (output / "dtc-reset-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result
