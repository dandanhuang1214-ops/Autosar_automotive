from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding
from automotive_workbench.dtc_aging import _CycleState, _apply_cycle_event
from automotive_workbench.dtc_intent import load_dtc_intent


def _cleared_state() -> _CycleState:
    return _CycleState(status=0, state="absent")


def _state_checksum(state: _CycleState) -> str:
    payload = json.dumps(
        asdict(state),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class _PersistentMirror:
    state: _CycleState
    checksum: str

    @classmethod
    def from_state(cls, state: _CycleState) -> _PersistentMirror:
        copied = copy.deepcopy(state)
        return cls(state=copied, checksum=_state_checksum(copied))

    def integrity_valid(self) -> bool:
        return self.checksum == _state_checksum(self.state)


def _apply_fault_event(
    runtime: _CycleState,
    mirror: _PersistentMirror,
    event: str,
    definition: dict[str, Any],
) -> tuple[_CycleState, _PersistentMirror, str, str]:
    if event in {"operation_cycle_start", "operation_cycle_end", "fault_present"}:
        try:
            _apply_cycle_event(runtime, event, definition)
        except ValueError as exc:
            return runtime, mirror, "DTC-PERSISTENCE-SEQUENCE", str(exc)
        return runtime, mirror, "", ""
    if event == "flush":
        if runtime.cycle_active:
            return runtime, mirror, "DTC-PERSISTENCE-SEQUENCE", "flush requires an inactive operation cycle"
        return runtime, _PersistentMirror.from_state(runtime), "", ""
    if event == "inject_flush_failure":
        return (
            runtime,
            mirror,
            "DTC-PERSISTENCE-FLUSH-FAILED",
            "Injected flush failure left the previous persistent mirror unchanged",
        )
    if event == "corrupt_mirror":
        mirror.checksum = "0" * 64
        return (
            runtime,
            mirror,
            "DTC-PERSISTENCE-MIRROR-CORRUPTED",
            "Injected checksum corruption into the persistent mirror",
        )
    if event == "hard_reset":
        if not mirror.integrity_valid():
            return (
                _cleared_state(),
                mirror,
                "DTC-PERSISTENCE-RESTORE-FAILED",
                "Persistent mirror checksum mismatch; restored empty safe runtime state",
            )
        restored = copy.deepcopy(mirror.state)
        restored.cycle_active = False
        restored.tested_this_cycle = False
        restored.failed_this_cycle = False
        return restored, mirror, "", ""
    return runtime, mirror, "DTC-PERSISTENCE-SEQUENCE", f"unsupported persistence event: {event}"


def run_dtc_persistence_fault_lab(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {int(item["code"]): item for item in payload["dtcs"]}
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["persistence_fault_experiments"]:
        definition = dtcs[int(experiment["dtc"])]
        runtime = _CycleState()
        mirror = _PersistentMirror.from_state(_cleared_state())
        for index, step in enumerate(experiment["steps"]):
            runtime, mirror, actual_finding, message = _apply_fault_event(
                runtime,
                mirror,
                str(step["event"]),
                definition,
            )
            expected_finding = str(step["expected_finding"])
            integrity = mirror.integrity_valid()
            runtime_extended = runtime.confirmed_once
            persistent_extended = mirror.state.confirmed_once
            passed = all([
                runtime.state == step["expected_runtime_state"],
                runtime.status == step["expected_runtime_status"],
                mirror.state.status == step["expected_persistent_status"],
                bool(runtime.snapshot) == step["expected_runtime_snapshot_stored"],
                bool(mirror.state.snapshot) == step["expected_persistent_snapshot_stored"],
                runtime_extended == step["expected_runtime_extended_data_stored"],
                persistent_extended == step["expected_persistent_extended_data_stored"],
                integrity == step["expected_mirror_integrity"],
                actual_finding == expected_finding,
            ])
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
                "runtime_status_hex": f"0x{runtime.status:02X}",
                "expected_persistent_status_hex": f"0x{int(step['expected_persistent_status']):02X}",
                "persistent_status_hex": f"0x{mirror.state.status:02X}",
                "runtime_snapshot_stored": bool(runtime.snapshot),
                "persistent_snapshot_stored": bool(mirror.state.snapshot),
                "runtime_extended_data_stored": runtime_extended,
                "persistent_extended_data_stored": persistent_extended,
                "expected_mirror_integrity": step["expected_mirror_integrity"],
                "mirror_integrity": integrity,
                "mirror_checksum": mirror.checksum,
                "expected_finding": expected_finding,
                "actual_finding": actual_finding,
                "message": message,
            }
            traces.append(trace)
            if actual_finding:
                findings.append(Finding(
                    code=actual_finding,
                    severity="ERROR",
                    message=message,
                    source_artifact=str(intent),
                    kind="dtc-persistence-fault",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())
            if not passed and not actual_finding:
                findings.append(Finding(
                    code="DTC-PERSISTENCE-FAULT-MISMATCH",
                    severity="ERROR",
                    message=f"{experiment['name']} step {index} did not match expected fault evidence",
                    source_artifact=str(intent),
                    kind="dtc-persistence-fault",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    passed_count = sum(item["status"] == "passed" for item in traces)
    result = {
        "artifact_type": "dtc-persistence-fault-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if passed_count == len(traces) else "failed",
        "ecu": payload["ecu"],
        "experiment_count": len(payload["persistence_fault_experiments"]),
        "step_count": len(traces),
        "passed_count": passed_count,
        "expected_fault_count": sum(bool(item["expected_finding"]) for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-persistence-fault-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Persistence Fault Report",
        "",
        f"- Status: **{result['status']}**",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        f"- Expected faults: {result['expected_fault_count']}",
        "",
        "| Step | Event | Runtime | Persistent | Integrity | Finding | Result |",
        "|---:|---|---|---|---|---|---|",
    ]
    for item in traces:
        lines.append(
            f"| {item['step']} | `{item['event']}` | `{item['runtime_status_hex']}` | "
            f"`{item['persistent_status_hex']}` | {item['mirror_integrity']} | "
            f"`{item['actual_finding']}` | {item['status']} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "SHA-256 and the in-process mirror provide deterministic fault evidence only. This is not AUTOSAR NvM, CRC configuration, retry, redundancy, flash, or safety proof.",
        "",
    ])
    (output / "dtc-persistence-fault-report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return result
