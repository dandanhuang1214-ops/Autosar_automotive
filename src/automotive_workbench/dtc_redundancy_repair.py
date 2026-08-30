from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.domain import Finding
from automotive_workbench.dtc_aging import _CycleState, _apply_cycle_event
from automotive_workbench.dtc_intent import load_dtc_intent
from automotive_workbench.dtc_redundancy import _Copy, _cleared_state, _select_copy


@dataclass
class _RepairContext:
    runtime: _CycleState
    copies: dict[str, _Copy]
    selected_copy: str = ""
    pending_kind: str = ""


def _target_copy(copies: dict[str, _Copy]) -> str:
    return min(copies, key=lambda name: (copies[name].generation, name))


def _restore(context: _RepairContext) -> tuple[str, str]:
    selected, finding, message = _select_copy(context.copies)
    context.selected_copy = selected
    context.pending_kind = ""
    if not selected:
        context.runtime = _cleared_state()
        return finding, message
    context.runtime = copy.deepcopy(context.copies[selected].state)
    context.runtime.cycle_active = False
    context.runtime.tested_this_cycle = False
    context.runtime.failed_this_cycle = False
    return finding, message


def _repair(context: _RepairContext, staged: bool) -> tuple[str, str, str]:
    source_name = context.selected_copy
    if not source_name or not context.copies[source_name].selectable():
        return (
            "refused",
            "DTC-REDUNDANCY-REPAIR-REFUSED",
            "Repair requires a valid committed source selected by restore",
        )

    peer_name = "B" if source_name == "A" else "A"
    source = context.copies[source_name]
    peer = context.copies[peer_name]
    if peer.selectable() and peer.generation == source.generation and peer.content_key() == source.content_key():
        return "no-op", "", "Redundant copies already agree"

    context.copies[peer_name] = _Copy.from_state(
        source.state,
        source.generation,
        committed=not staged,
    )
    if staged:
        context.pending_kind = "repair"
        return "staged", "", f"Staged repair of copy {peer_name} from copy {source_name}"
    context.pending_kind = ""
    return "committed", "", f"Repaired copy {peer_name} from copy {source_name}"


def _apply_event(
    context: _RepairContext,
    event: str,
    definition: dict[str, Any],
) -> tuple[str, str, str]:
    if event in {"operation_cycle_start", "operation_cycle_end", "fault_present"}:
        try:
            _apply_cycle_event(context.runtime, event, definition)
        except ValueError as exc:
            return "", "DTC-REDUNDANCY-SEQUENCE", str(exc)
        return "", "", ""
    if event == "flush":
        if context.runtime.cycle_active:
            return "", "DTC-REDUNDANCY-SEQUENCE", "flush requires an inactive operation cycle"
        target = _target_copy(context.copies)
        generation = max(item.generation for item in context.copies.values()) + 1
        context.copies[target] = _Copy.from_state(context.runtime, generation)
        context.selected_copy = ""
        context.pending_kind = ""
        return "committed", "", f"Wrote copy {target} at generation {generation}"
    if event == "stage_flush":
        if context.runtime.cycle_active:
            return "", "DTC-REDUNDANCY-SEQUENCE", "stage_flush requires an inactive operation cycle"
        target = _target_copy(context.copies)
        generation = max(item.generation for item in context.copies.values()) + 1
        context.copies[target] = _Copy.from_state(
            context.runtime,
            generation,
            committed=False,
        )
        context.selected_copy = ""
        context.pending_kind = "write"
        return "staged", "", f"Staged copy {target} at generation {generation}"
    if event == "interrupt_write":
        if context.pending_kind != "write":
            return "", "DTC-REDUNDANCY-SEQUENCE", "No staged normal write is active"
        context.pending_kind = ""
        return (
            "interrupted",
            "DTC-REDUNDANCY-WRITE-INTERRUPTED",
            "Interrupted staged normal write before commit",
        )
    if event == "hard_reset":
        finding, message = _restore(context)
        return "", finding, message
    if event == "repair":
        return _repair(context, staged=False)
    if event == "stage_repair":
        return _repair(context, staged=True)
    if event == "interrupt_repair":
        if context.pending_kind != "repair":
            return "", "DTC-REDUNDANCY-SEQUENCE", "No staged repair is active"
        context.pending_kind = ""
        return (
            "interrupted",
            "DTC-REDUNDANCY-REPAIR-INTERRUPTED",
            "Interrupted staged repair before commit",
        )
    return "", "DTC-REDUNDANCY-SEQUENCE", f"unsupported redundancy repair event: {event}"


def run_dtc_redundancy_repair_lab(intent: Path, output: Path) -> dict[str, Any]:
    payload = load_dtc_intent(intent)
    dtcs = {int(item["code"]): item for item in payload["dtcs"]}
    traces: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for experiment in payload["redundancy_repair_experiments"]:
        definition = dtcs[int(experiment["dtc"])]
        context = _RepairContext(
            runtime=_CycleState(),
            copies={
                "A": _Copy.from_state(_cleared_state(), 0),
                "B": _Copy.from_state(_cleared_state(), 0),
            },
        )
        for index, step in enumerate(experiment["steps"]):
            repair_outcome, actual_finding, message = _apply_event(
                context,
                str(step["event"]),
                definition,
            )
            expected_finding = str(step["expected_finding"])
            passed = all([
                context.runtime.state == step["expected_runtime_state"],
                context.runtime.status == step["expected_runtime_status"],
                context.copies["A"].state.status == step["expected_copy_a_status"],
                context.copies["B"].state.status == step["expected_copy_b_status"],
                context.copies["A"].generation == step["expected_copy_a_generation"],
                context.copies["B"].generation == step["expected_copy_b_generation"],
                context.copies["A"].integrity_valid() == step["expected_copy_a_integrity"],
                context.copies["B"].integrity_valid() == step["expected_copy_b_integrity"],
                context.copies["A"].committed == step["expected_copy_a_committed"],
                context.copies["B"].committed == step["expected_copy_b_committed"],
                context.selected_copy == step["expected_selected_copy"],
                repair_outcome == step["expected_repair_outcome"],
                actual_finding == expected_finding,
            ])
            trace = {
                "experiment": experiment["name"],
                "step": index,
                "event": step["event"],
                "status": "passed" if passed else "failed",
                "dtc_hex": f"0x{int(definition['code']):06X}",
                "runtime_state": context.runtime.state,
                "runtime_status_hex": f"0x{context.runtime.status:02X}",
                "copy_a_status_hex": f"0x{context.copies['A'].state.status:02X}",
                "copy_b_status_hex": f"0x{context.copies['B'].state.status:02X}",
                "copy_a_generation": context.copies["A"].generation,
                "copy_b_generation": context.copies["B"].generation,
                "copy_a_integrity": context.copies["A"].integrity_valid(),
                "copy_b_integrity": context.copies["B"].integrity_valid(),
                "copy_a_committed": context.copies["A"].committed,
                "copy_b_committed": context.copies["B"].committed,
                "selected_copy": context.selected_copy,
                "repair_outcome": repair_outcome,
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
                    kind="dtc-redundancy-repair",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())
            if not passed and not actual_finding:
                findings.append(Finding(
                    code="DTC-REDUNDANCY-REPAIR-MISMATCH",
                    severity="ERROR",
                    message=f"{experiment['name']} step {index} did not match expected repair evidence",
                    source_artifact=str(intent),
                    kind="dtc-redundancy-repair",
                    location=f"{experiment['name']}.steps[{index}]",
                ).to_dict())

    timestamp = datetime.now(timezone.utc)
    passed_count = sum(item["status"] == "passed" for item in traces)
    result = {
        "artifact_type": "dtc-redundancy-repair-lab",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if passed_count == len(traces) else "failed",
        "ecu": payload["ecu"],
        "experiment_count": len(payload["redundancy_repair_experiments"]),
        "step_count": len(traces),
        "passed_count": passed_count,
        "expected_fault_count": sum(bool(item["expected_finding"]) for item in traces),
        "traces": traces,
        "finding_count": len(findings),
        "findings": findings,
        "artifacts": [str(intent)],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dtc-redundancy-repair-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# DTC Redundancy Repair Report",
        "",
        f"- Status: **{result['status']}**",
        f"- Steps: {result['passed_count']}/{result['step_count']} passed",
        f"- Expected faults: {result['expected_fault_count']}",
        "",
        "| Experiment | Step | Event | Runtime | Copy A | Copy B | Selected | Repair | Finding | Result |",
        "|---|---:|---|---|---|---|---|---|---|---|",
    ]
    for item in traces:
        a_commit = "C" if item["copy_a_committed"] else "U"
        b_commit = "C" if item["copy_b_committed"] else "U"
        lines.append(
            f"| `{item['experiment']}` | {item['step']} | `{item['event']}` | "
            f"`{item['runtime_status_hex']}` | `g{item['copy_a_generation']} {a_commit} {item['copy_a_status_hex']}` | "
            f"`g{item['copy_b_generation']} {b_commit} {item['copy_b_status_hex']}` | "
            f"`{item['selected_copy']}` | `{item['repair_outcome']}` | "
            f"`{item['actual_finding']}` | {item['status']} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "Commit markers and repair ordering are deterministic Workbench policy. This is not AUTOSAR NvM job behavior, flash atomicity, wear handling, or safety proof.",
        "",
    ])
    (output / "dtc-redundancy-repair-report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return result
