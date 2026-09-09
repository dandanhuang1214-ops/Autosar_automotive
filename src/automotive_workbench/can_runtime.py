from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.applicability import build_runtime_applicability_profile

from automotive_workbench.adapters.dbc import _load_dbc


def _python_can() -> Any:
    try:
        import can
    except ImportError as exc:
        raise RuntimeError(
            'CAN runtime requires the optional dependency: pip install -e ".[can]"'
        ) from exc
    return can


def _scenario(name: str, expected: str, observed: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {
        "scenario": name,
        "status": "passed" if passed else "failed",
        "expected": expected,
        "observed": observed,
        "evidence": evidence,
    }


def _round_trip(database: Any, sender: Any, receiver: Any, can: Any) -> dict[str, Any]:
    definition = database.get_message_by_name("WindowStatus")
    values = {"WindowPosition": 42, "AntiPinchActive": 1, "MotorRequest": 2}
    payload = definition.encode(values)
    sender.send(can.Message(arbitration_id=definition.frame_id, data=payload, is_extended_id=False))
    received = receiver.recv(timeout=0.2)
    decoded = definition.decode(received.data, decode_choices=False) if received else None
    passed = received is not None and received.arbitration_id == definition.frame_id and decoded == values
    return _scenario(
        "round_trip",
        "receive frame 0x100 and decode all three physical values",
        "decoded" if passed else "missing or mismatched frame",
        passed,
        message_name=definition.name,
        direction="tx",
        frame_id=None if received is None else received.arbitration_id,
        payload_hex=payload.hex().upper(),
        decoded=decoded,
    )


def _command_receive(database: Any, peer: Any, local: Any, can: Any) -> dict[str, Any]:
    definition = database.get_message_by_name("WindowCommand")
    values = {"RequestedDirection": 2}
    payload = definition.encode(values)
    peer.send(can.Message(arbitration_id=definition.frame_id, data=payload, is_extended_id=False))
    received = local.recv(timeout=0.2)
    decoded = definition.decode(received.data, decode_choices=False) if received else None
    passed = received is not None and received.arbitration_id == definition.frame_id and decoded == values
    return _scenario(
        "command_receive",
        "BODY_ECU receives frame 0x200 and decodes RequestedDirection",
        "decoded" if passed else "missing or mismatched frame",
        passed,
        message_name=definition.name,
        direction="rx",
        frame_id=None if received is None else received.arbitration_id,
        payload_hex=payload.hex().upper(),
        decoded=decoded,
    )


def _wrong_can_id(sender: Any, receiver: Any, can: Any) -> dict[str, Any]:
    sender.send(can.Message(arbitration_id=0x101, data=bytes(8), is_extended_id=False))
    received = receiver.recv(timeout=0.2)
    detected = received is not None and received.arbitration_id != 0x100
    return _scenario(
        "wrong_can_id",
        "receiver detects frame ID is not WindowStatus 0x100",
        "unexpected ID detected" if detected else "fault not detected",
        detected,
        expected_frame_id=0x100,
        actual_frame_id=None if received is None else received.arbitration_id,
    )


def _receive_timeout(receiver: Any) -> dict[str, Any]:
    received = receiver.recv(timeout=0.03)
    detected = received is None
    return _scenario(
        "receive_timeout",
        "no frame arrives before timeout",
        "timeout detected" if detected else "unexpected frame received",
        detected,
        timeout_ms=30,
    )


def _invalid_physical_value(database: Any) -> dict[str, Any]:
    definition = database.get_message_by_name("WindowStatus")
    try:
        definition.encode({"WindowPosition": 101, "AntiPinchActive": 0, "MotorRequest": 0})
    except Exception as exc:
        return _scenario(
            "invalid_physical_value",
            "cantools rejects WindowPosition above physical maximum 100",
            type(exc).__name__,
            True,
            attempted_value=101,
            error=str(exc),
        )
    return _scenario(
        "invalid_physical_value",
        "cantools rejects WindowPosition above physical maximum 100",
        "invalid value was encoded",
        False,
        attempted_value=101,
    )


def render_can_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Virtual CAN Runtime Report",
        "",
        f"- Run ID: `{result['run_id']}`",
        f"- Backend: `{result['backend']}`",
        f"- Status: **{result['status']}**",
        f"- Scenarios: {result['passed_count']}/{result['scenario_count']} passed",
        "",
        "| Scenario | Result | Expected | Observed |",
        "|---|---|---|---|",
    ]
    for scenario in result["scenarios"]:
        lines.append(
            f"| `{scenario['scenario']}` | {scenario['status']} | {scenario['expected']} | {scenario['observed']} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "The python-can virtual backend proves application-level frame exchange in one process. It does not emulate CAN arbitration, electrical faults, a CAN controller, SocketCAN, or production ECU timing.",
        "",
    ])
    return "\n".join(lines)


def run_can_lab(dbc: Path, output: Path) -> dict[str, Any]:
    can = _python_can()
    database = _load_dbc(dbc)
    channel = f"automotive-workbench-{uuid.uuid4()}"
    sender = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    receiver = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    started = time.perf_counter()
    try:
        scenarios = [
            _round_trip(database, sender, receiver, can),
            _command_receive(database, sender, receiver, can),
            _wrong_can_id(sender, receiver, can),
            _receive_timeout(receiver),
            _invalid_physical_value(database),
        ]
    finally:
        sender.shutdown()
        receiver.shutdown()
    passed_count = sum(item["status"] == "passed" for item in scenarios)
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "virtual-can-runtime",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "backend": "python-can virtual",
        "applicability_profile": build_runtime_applicability_profile(
            variant=dbc.stem,
            software_version="can-lab-0.2",
            inputs=[dbc],
            backend="python-can virtual",
        ),
        "status": "passed" if passed_count == len(scenarios) else "failed",
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "artifacts": [str(dbc)],
        "scenarios": scenarios,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "can-runtime-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "can-runtime-report.md").write_text(render_can_markdown(result), encoding="utf-8")
    return result
