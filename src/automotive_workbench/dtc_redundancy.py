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


def _checksum(state: _CycleState, generation: int) -> str:
    payload = json.dumps(
        {"generation": generation, "state": asdict(state)},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class _Copy:
    state: _CycleState
    generation: int
    checksum: str

    @classmethod
    def from_state(cls, state: _CycleState, generation: int) -> _Copy:
        copied = copy.deepcopy(state)
        return cls(copied, generation, _checksum(copied, generation))

    def integrity_valid(self) -> bool:
        return self.checksum == _checksum(self.state, self.generation)

    def content_key(self) -> str:
        return json.dumps(asdict(self.state), sort_keys=True, separators=(",", ":"))


def _select_copy(copies: dict[str, _Copy]) -> tuple[str, str, str]:
    valid = [(name, item) for name, item in copies.items() if item.integrity_valid()]
    if not valid:
        return "", "DTC-REDUNDANCY-RESTORE-FAILED", "No valid redundant copy is available"
    if len(valid) == 1:
        name, _ = valid[0]
        return name, "DTC-REDUNDANCY-LOSS", f"Only copy {name} is valid"

    (name_a, copy_a), (name_b, copy_b) = valid
    if copy_a.generation == copy_b.generation:
        if copy_a.content_key() != copy_b.content_key():
            return (
                "",
                "DTC-REDUNDANCY-ARBITRATION-FAILED",
                "Valid copies have equal generation but divergent content",
            )
        return name_a, "", "Redundant copies agree"

    selected = name_a if copy_a.generation > copy_b.generation else name_b
    return selected, "DTC-REDUNDANCY-LOSS", f"Copies diverge; selected newer copy {selected}"


def _apply_event(
    runtime: _CycleState,
    copies: dict[str, _Copy],
    event: str,
    definition: dict[str, Any],
) -> tuple[_CycleState, str, str, str]:
    if event in {"operation_cycle_start", "operation_cycle_end", "fault_present"}:
        try:
            _apply_cycle_event(runtime, event, definition)
        except ValueError as exc:
            return runtime, "", "DTC-REDUNDANCY-SEQUENCE", str(exc)
        return runtime, "", "", ""
    if event == "flush":
        if runtime.cycle_active:
            return runtime, "", "DTC-REDUNDANCY-SEQUENCE", "flush requires an inactive operation cycle"
        target = min(copies, key=lambda name: (copies[name].generation, name))
        generation = max(item.generation for item in copies.values()) + 1
        copies[target] = _Copy.from_state(runtime, generation)
        return runtime, "", "", f"Wrote copy {target} at generation {generation}"
    if event == "corrupt_copy_a":
        copies["A"].checksum = "0" * 64
        return runtime, "", "DTC-REDUNDANCY-COPY-CORRUPTED", "Injected checksum corruption into copy A"
    if event == "hard_reset":
        selected, finding, message = _select_copy(copies)
        if not selected:
            return _cleared_state(), "", finding, message
        restored = copy.deepcopy(copies[selected].state)
        restored.cycle_active = False
        restored.tested_this_cycle = False
        restored.failed_this_cycle = False
        return restored, selected, finding, message
    return runtime, "", "DTC-REDUNDANCY-SEQUENCE", f"unsupported redundancy event: {event}"


def run_dtc_redundancy_lab(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {int(item["code"]): item for item in payload["dtcs"]}
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["redundancy_experiments"]:
        definition = dtcs[int(experiment["dtc"])]
        runtime = _CycleState()
        copies = {
            "A": _Copy.from_state(_cleared_state(), 0),
            "B": _Copy.from_state(_cleared_state(), 0),
        }
        for index, step in enumerate(experiment["steps"]):
            runtime, selected, actual_finding, message = _apply_event(
                runtime, copies, str(step["event"]), definition
            )
            expected_finding = str(step["expected_finding"])
            passed = all([
                runtime.state == step["expected_runtime_state"],
                runtime.status == step["expected_runtime_status"],
                copies["A"].state.status == step["expected_copy_a_status"],
                copies["B"].state.status == step["expected_copy_b_status"],
                copies["A"].generation == step["expected_copy_a_generation"],
                copies["B"].generation == step["expected_copy_b_generation"],
                copies["A"].integrity_valid() == step["expected_copy_a_integrity"],
                copies["B"].integrity_valid() == step["expected_copy_b_integrity"],
                selected == step["expected_selected_copy"],
                actual_finding == expected_finding,
            ])
            trace = {
                "experiment": experiment["name"],
                "step": index,
                "event": step["event"],
                "status": "passed" if passed else "failed",
                "dtc_hex": f"0x{int(definition['code']):06X}",
                "runtime_state": runtime.state,
                "runtime_status_hex": f"0x{runtime.status:02X}",
                "copy_a_status_hex": f"0x{copies['A'].state.status:02X}",
                "copy_b_status_hex": f"0x{copies['B'].state.status:02X}",
                "copy_a_generation": copies["A"].generation,
                "copy_b_generation": copies["B"].generation,
                "copy_a_integrity": copies["A"].integrity_valid(),
                "copy_b_integrity": copies["B"].integrity_valid(),
                "selected_copy": selected,
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
                    kind="dtc-redundancy",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())
            if not passed and not actual_finding:
                findings.append(Finding(
                    code="DTC-REDUNDANCY-MISMATCH",
                    severity="ERROR",
                    message=f"{experiment['name']} step {index} did not match expected redundancy evidence",
                    source_artifact=str(intent),
                    kind="dtc-redundancy",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    passed_count = sum(item["status"] == "passed" for item in traces)
    result = {
        "artifact_type": "dtc-redundancy-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if passed_count == len(traces) else "failed",
        "ecu": payload["ecu"],
        "experiment_count": len(payload["redundancy_experiments"]),
        "step_count": len(traces),
        "passed_count": passed_count,
        "expected_fault_count": sum(bool(item["expected_finding"]) for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-redundancy-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Redundancy Report",
        "",
        f"- Status: **{result['status']}**",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        f"- Expected faults: {result['expected_fault_count']}",
        "",
        "| Step | Event | Runtime | Copy A | Copy B | Selected | Finding | Result |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for item in traces:
        lines.append(
            f"| {item['step']} | `{item['event']}` | `{item['runtime_status_hex']}` | "
            f"`g{item['copy_a_generation']} {item['copy_a_status_hex']}` | "
            f"`g{item['copy_b_generation']} {item['copy_b_status_hex']}` | "
            f"`{item['selected_copy']}` | `{item['actual_finding']}` | {item['status']} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "Generation ordering and SHA-256 envelopes are deterministic Workbench policy. This is not AUTOSAR NvM redundant-block behavior, flash atomicity, wear handling, or safety proof.",
        "",
    ])
    (output / "dtc-redundancy-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result
