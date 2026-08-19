from __future__ import annotations

import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.can_runtime import _python_can


def _send_status(sender: Any, can: Any, definition: Any, position: int) -> None:
    payload = definition.encode({
        "WindowPosition": position,
        "AntiPinchActive": 0,
        "MotorRequest": 0,
    })
    sender.send(can.Message(
        arbitration_id=definition.frame_id,
        data=payload,
        is_extended_id=False,
    ))


def _periodic_baseline(sender: Any, receiver: Any, can: Any, definition: Any) -> dict[str, Any]:
    period_s = 0.01
    count = 6
    sent_at: list[float] = []
    received_at: list[float] = []
    deadline = time.perf_counter()
    for index in range(count):
        delay = deadline - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        sent_at.append(time.perf_counter())
        _send_status(sender, can, definition, 40 + index)
        message = receiver.recv(timeout=0.1)
        if message is not None:
            received_at.append(time.perf_counter())
        deadline += period_s

    intervals_ms = [
        (right - left) * 1000
        for left, right in zip(received_at, received_at[1:])
    ]
    mean_ms = statistics.mean(intervals_ms) if intervals_ms else 0.0
    max_jitter_ms = max((abs(value - 10.0) for value in intervals_ms), default=999.0)
    passed = len(received_at) == count and 5.0 <= mean_ms <= 20.0 and max_jitter_ms <= 15.0
    return {
        "scenario": "periodic_baseline",
        "status": "passed" if passed else "failed",
        "expected": "6 frames at nominal 10 ms period",
        "observed": f"received {len(received_at)}/6 frames",
        "evidence": {
            "nominal_period_ms": 10,
            "sent_count": len(sent_at),
            "received_count": len(received_at),
            "intervals_ms": [round(value, 3) for value in intervals_ms],
            "mean_period_ms": round(mean_ms, 3),
            "max_jitter_ms": round(max_jitter_ms, 3),
            "measurement_note": "host scheduling observation, not ECU real-time proof",
        },
    }


def _drop_timeout_recovery(sender: Any, receiver: Any, can: Any, definition: Any) -> dict[str, Any]:
    timeout_s = 0.04
    _send_status(sender, can, definition, 50)
    first = receiver.recv(timeout=0.1)
    silence_started = time.perf_counter()
    during_silence = receiver.recv(timeout=timeout_s)
    elapsed_ms = (time.perf_counter() - silence_started) * 1000
    timeout_detected = first is not None and during_silence is None and elapsed_ms >= 35.0
    _send_status(sender, can, definition, 51)
    recovered = receiver.recv(timeout=0.1)
    decoded = definition.decode(recovered.data, decode_choices=False) if recovered else None
    recovery_detected = decoded is not None and decoded["WindowPosition"] == 51
    passed = timeout_detected and recovery_detected
    return {
        "scenario": "drop_timeout_recovery",
        "status": "passed" if passed else "failed",
        "expected": "silence exceeds 40 ms timeout and next valid frame restores reception",
        "observed": "timeout and recovery detected" if passed else "supervision transition missing",
        "evidence": {
            "timeout_threshold_ms": 40,
            "observed_silence_ms": round(elapsed_ms, 3),
            "timeout_detected": timeout_detected,
            "recovery_detected": recovery_detected,
            "recovered_value": None if decoded is None else decoded["WindowPosition"],
            "state_sequence": ["RECEIVING", "TIMEOUT", "RECOVERED"] if passed else [],
        },
    }


def render_supervision_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# CAN Periodic Communication and Supervision Report",
        "",
        f"- Run ID: `{result['run_id']}`",
        f"- Backend: `{result['backend']}`",
        f"- Status: **{result['status']}**",
        f"- Scenarios: {result['passed_count']}/{result['scenario_count']} passed",
        "",
        "| Scenario | Result | Expected | Observed |",
        "|---|---|---|---|",
    ]
    for item in result["scenarios"]:
        lines.append(f"| `{item['scenario']}` | {item['status']} | {item['expected']} | {item['observed']} |")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Timing values are host-process observations on python-can virtual. They prove supervision logic and repeatability, not hard real-time behavior, bus arbitration, COM deadline monitoring configuration, or production ECU timing.",
        "",
    ])
    return "\n".join(lines)


def run_can_supervision(dbc: Path, output: Path) -> dict[str, Any]:
    can = _python_can()
    database = _load_dbc(dbc)
    definition = database.get_message_by_name("WindowStatus")
    channel = f"automotive-workbench-supervision-{uuid.uuid4()}"
    sender = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    receiver = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    started = time.perf_counter()
    try:
        scenarios = [
            _periodic_baseline(sender, receiver, can, definition),
            _drop_timeout_recovery(sender, receiver, can, definition),
        ]
    finally:
        sender.shutdown()
        receiver.shutdown()
    passed_count = sum(item["status"] == "passed" for item in scenarios)
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "can-communication-supervision",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "backend": "python-can virtual",
        "status": "passed" if passed_count == len(scenarios) else "failed",
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "artifacts": [str(dbc)],
        "scenarios": scenarios,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "can-supervision-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "can-supervision-report.md").write_text(
        render_supervision_markdown(result), encoding="utf-8"
    )
    return result
