from __future__ import annotations

import json
import platform
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import BusConfig, capture_log, decode_log, open_bus, replay_log
from automotive_workbench.can_runtime import _python_can


def _fault_scenario(name: str, expected: str, observed: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {
        "scenario": name,
        "status": "passed" if passed else "failed",
        "expected": expected,
        "observed": observed,
        "evidence": evidence,
    }


def _interface_exists(name: str) -> bool:
    try:
        socket.if_nametoindex(name)
    except OSError:
        return False
    return True


def probe_can_backend(config: BusConfig, output: Path | None = None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "system": platform.system(),
        "platform": sys.platform,
        "release": platform.release(),
        "python": platform.python_version(),
        "interface": config.interface,
        "channel": config.channel,
    }
    reason = ""
    status = "available"
    capabilities = {
        "open": False,
        "send": False,
        "receive": False,
        "capture": False,
        "replay": False,
    }

    if config.interface == "socketcan" and sys.platform != "linux":
        status = "blocked"
        reason = "unsupported_platform"
    elif config.interface == "socketcan" and not _interface_exists(config.channel):
        status = "blocked"
        reason = "interface_missing"
    else:
        try:
            bus = open_bus(config)
        except Exception as exc:
            status = "blocked"
            reason = "backend_open_failed"
            evidence["error_type"] = type(exc).__name__
            evidence["error"] = str(exc)
        else:
            capabilities = {key: True for key in capabilities}
            capabilities["open"] = True
            evidence["channel_info"] = str(bus.channel_info)
            bus.shutdown()

    result = {
        "artifact_type": "can-backend-capability",
        "status": status,
        "reason": reason,
        "config": {
            "interface": config.interface,
            "channel": config.channel,
            "receive_own_messages": config.receive_own_messages,
            "fd": config.fd,
        },
        "capabilities": capabilities,
        "evidence": evidence,
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "backend-probe.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        markdown = [
            "# CAN Backend Probe",
            "",
            f"- Status: **{status}**",
            f"- Reason: `{reason or 'none'}`",
            f"- Interface: `{config.interface}`",
            f"- Channel: `{config.channel}`",
            f"- Host: `{evidence['system']} {evidence['release']}`",
            "",
            "| Capability | Available |",
            "|---|---|",
        ]
        for name, available in capabilities.items():
            markdown.append(f"| {name} | {available} |")
        (output / "backend-probe.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return result


def run_backend_lab(dbc_path: Path, config: BusConfig, output: Path) -> dict[str, Any]:
    probe = probe_can_backend(config, output / "probe")
    if probe["status"] != "available":
        result = {
            "artifact_type": "can-backend-lab",
            "status": "blocked",
            "reason": probe["reason"],
            "probe": probe,
            "replay_integrity": False,
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "backend-lab-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    can = _python_can()
    sender = open_bus(config)
    receiver = open_bus(config)
    try:
        for value in (60, 61, 62):
            sender.send(can.Message(
                arbitration_id=0x100,
                data=bytes([value, 0, 0, 0, 0, 0, 0, 0]),
                is_extended_id=False,
            ))
            time.sleep(0.005)
        capture = capture_log(receiver, output / "capture", 3, 1.0, config)
        log_path = output / "capture" / "capture.log"
        analysis = decode_log(log_path, dbc_path, output / "decode")
        replay = replay_log(
            log_path,
            sender,
            timestamps=False,
            gap_s=0.001,
            output=output / "replay",
            config=config,
        )
        replayed = [receiver.recv(timeout=0.2) for _ in range(replay["sent_count"])]
        sender.send(can.Message(arbitration_id=0x101, data=bytes(8), is_extended_id=False))
        wrong_id = receiver.recv(timeout=0.2)
        receive_timeout = receiver.recv(timeout=0.03)
    finally:
        sender.shutdown()
        receiver.shutdown()

    replay_integrity = all(message is not None for message in replayed) and [
        (message.arbitration_id, bytes(message.data)) for message in replayed
    ] == [
        (item["frame_id"], bytes.fromhex(item["payload_hex"]))
        for item in analysis["decoded"]
    ]
    fault_scenarios = [
        _fault_scenario(
            "wrong_arbitration_id",
            "receiver detects frame ID is not WindowStatus 0x100",
            "unexpected ID detected" if wrong_id is not None and wrong_id.arbitration_id != 0x100 else "fault not detected",
            wrong_id is not None and wrong_id.arbitration_id != 0x100,
            expected_frame_id=0x100,
            actual_frame_id=None if wrong_id is None else wrong_id.arbitration_id,
        ),
        _fault_scenario(
            "receive_timeout",
            "no frame arrives before timeout",
            "timeout detected" if receive_timeout is None else "unexpected frame received",
            receive_timeout is None,
            timeout_ms=30,
        ),
    ]
    passed = (
        capture["status"] == "passed"
        and analysis["status"] == "passed"
        and replay["status"] == "passed"
        and replay_integrity
        and all(item["status"] == "passed" for item in fault_scenarios)
    )
    result = {
        "artifact_type": "can-backend-lab",
        "status": "passed" if passed else "failed",
        "reason": "",
        "probe": probe,
        "captured_count": capture["captured_count"],
        "decoded_count": analysis["decoded_count"],
        "finding_count": analysis["finding_count"],
        "replayed_count": replay["sent_count"],
        "replay_integrity": replay_integrity,
        "fault_scenarios": fault_scenarios,
        "log_sha256": capture["log_sha256"],
        "dbc_sha256": analysis["dbc_sha256"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "backend-lab-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def unique_virtual_config() -> BusConfig:
    return BusConfig("virtual", f"workbench-backend-{uuid.uuid4()}")
