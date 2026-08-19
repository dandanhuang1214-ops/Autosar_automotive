from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.can_runtime import _python_can
from automotive_workbench.domain import Finding


@dataclass(frozen=True)
class BusConfig:
    interface: str
    channel: str
    receive_own_messages: bool = False
    fd: bool = False


def open_bus(config: BusConfig) -> Any:
    can = _python_can()
    kwargs: dict[str, Any] = {
        "interface": config.interface,
        "channel": config.channel,
        "receive_own_messages": config.receive_own_messages,
        "ignore_config": True,
    }
    if config.interface != "virtual":
        kwargs["fd"] = config.fd
    return can.Bus(**kwargs)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def capture_log(
    bus: Any,
    output: Path,
    count: int,
    timeout_s: float,
    config: BusConfig | None = None,
) -> dict[str, Any]:
    if count <= 0:
        raise ValueError("capture count must be positive")
    if timeout_s <= 0:
        raise ValueError("capture timeout must be positive")
    can = _python_can()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "capture.log"
    writer = can.Logger(str(log_path))
    captured = 0
    started = time.perf_counter()
    try:
        while captured < count and time.perf_counter() - started < timeout_s:
            remaining = timeout_s - (time.perf_counter() - started)
            message = bus.recv(timeout=max(0.0, min(0.1, remaining)))
            if message is None:
                continue
            writer.on_message_received(message)
            captured += 1
    finally:
        writer.stop()
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "can-capture-manifest",
        "created_at": timestamp.isoformat(),
        "status": "passed" if captured == count else "failed",
        "requested_count": count,
        "captured_count": captured,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "log": str(log_path),
        "log_sha256": sha256_file(log_path),
        "format": "can-utils .log",
        "bus_config": None if config is None else asdict(config),
    }
    (output / "capture.manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def decode_log(log_path: Path, dbc_path: Path, output: Path) -> dict[str, Any]:
    can = _python_can()
    database = _load_dbc(dbc_path)
    messages_by_id = {message.frame_id: message for message in database.messages}
    findings: list[Finding] = []
    decoded: list[dict[str, Any]] = []
    frame_count = 0
    with can.LogReader(str(log_path)) as reader:
        for index, frame in enumerate(reader):
            frame_count += 1
            definition = messages_by_id.get(frame.arbitration_id)
            location = f"frame[{index}]"
            if definition is None:
                findings.append(Finding(
                    code="LOG-UNKNOWN-FRAME-ID",
                    severity="ERROR",
                    message=f"No DBC message for CAN ID 0x{frame.arbitration_id:X}",
                    source_artifact=str(log_path),
                    kind="can-frame",
                    field="arbitration_id",
                    location=location,
                ))
                continue
            if len(frame.data) != definition.length:
                findings.append(Finding(
                    code="LOG-DLC-MISMATCH",
                    severity="ERROR",
                    message=f"0x{frame.arbitration_id:X}: log DLC={len(frame.data)}, DBC DLC={definition.length}",
                    source_artifact=str(log_path),
                    kind="can-frame",
                    field="dlc",
                    location=location,
                ))
                continue
            try:
                values = definition.decode(frame.data, decode_choices=False)
            except Exception as exc:
                findings.append(Finding(
                    code="LOG-DECODE-ERROR",
                    severity="ERROR",
                    message=f"0x{frame.arbitration_id:X}: {exc}",
                    source_artifact=str(log_path),
                    kind="can-frame",
                    field="data",
                    location=location,
                ))
                continue
            decoded.append({
                "index": index,
                "timestamp": frame.timestamp,
                "frame_id": frame.arbitration_id,
                "message": definition.name,
                "payload_hex": frame.data.hex().upper(),
                "signals": values,
            })
    result = {
        "artifact_type": "can-log-analysis",
        "status": "passed" if not findings else "failed",
        "log": str(log_path),
        "log_sha256": sha256_file(log_path),
        "dbc": str(dbc_path),
        "dbc_sha256": sha256_file(dbc_path),
        "frame_count": frame_count,
        "decoded_count": len(decoded),
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
        "decoded": decoded,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "decode-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# CAN Log Decode Report",
        "",
        f"- Status: **{result['status']}**",
        f"- Frames: {result['frame_count']}",
        f"- Decoded: {result['decoded_count']}",
        f"- Findings: {result['finding_count']}",
        f"- Log SHA-256: `{result['log_sha256']}`",
        f"- DBC SHA-256: `{result['dbc_sha256']}`",
        "",
        "| Index | CAN ID | Message | Payload | Signals |",
        "|---:|---:|---|---|---|",
    ]
    for item in decoded:
        lines.append(
            f"| {item['index']} | `0x{item['frame_id']:X}` | {item['message']} | `{item['payload_hex']}` | `{json.dumps(item['signals'], ensure_ascii=False)}` |"
        )
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            lines.append(f"- `{finding.code}` — {finding.message}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Decoded values depend on the recorded DBC hash above. The raw log remains the source frame evidence.",
        "",
    ])
    (output / "decode-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def replay_log(
    log_path: Path,
    bus: Any,
    timestamps: bool = True,
    gap_s: float = 0.001,
    output: Path | None = None,
    config: BusConfig | None = None,
) -> dict[str, Any]:
    if gap_s < 0:
        raise ValueError("replay gap must not be negative")
    can = _python_can()
    sent = 0
    started = time.perf_counter()
    with can.LogReader(str(log_path)) as reader:
        synchronized = can.MessageSync(reader, timestamps=timestamps, gap=gap_s)
        for message in synchronized:
            bus.send(message)
            sent += 1
    result = {
        "artifact_type": "can-log-replay",
        "status": "passed",
        "log": str(log_path),
        "log_sha256": sha256_file(log_path),
        "timing_mode": "recorded" if timestamps else "fixed-gap",
        "gap_ms": None if timestamps else gap_s * 1000,
        "sent_count": sent,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "bus_config": None if config is None else asdict(config),
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "replay-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def run_log_lab(dbc_path: Path, output: Path) -> dict[str, Any]:
    can = _python_can()
    capture_channel = f"workbench-log-lab-{uuid.uuid4()}"
    capture_config = BusConfig("virtual", capture_channel)
    sender = open_bus(capture_config)
    receiver = open_bus(capture_config)
    try:
        for value in (40, 41, 42):
            sender.send(can.Message(
                arbitration_id=0x100,
                data=bytes([value, 0, 0, 0, 0, 0, 0, 0]),
                is_extended_id=False,
            ))
            time.sleep(0.005)
        capture = capture_log(receiver, output / "capture", 3, 1.0, capture_config)
    finally:
        sender.shutdown()
        receiver.shutdown()

    log_path = output / "capture" / "capture.log"
    analysis = decode_log(log_path, dbc_path, output / "decode")
    replay_channel = f"workbench-log-replay-{uuid.uuid4()}"
    replay_config = BusConfig("virtual", replay_channel)
    replay_sender = open_bus(replay_config)
    replay_receiver = open_bus(replay_config)
    try:
        replay = replay_log(
            log_path,
            replay_sender,
            timestamps=True,
            output=output / "replay",
            config=replay_config,
        )
        replayed = [replay_receiver.recv(timeout=0.1) for _ in range(replay["sent_count"])]
    finally:
        replay_sender.shutdown()
        replay_receiver.shutdown()
    replay_integrity = all(message is not None for message in replayed) and [
        (message.arbitration_id, bytes(message.data)) for message in replayed
    ] == [
        (item["frame_id"], bytes.fromhex(item["payload_hex"])) for item in analysis["decoded"]
    ]
    passed = (
        capture["status"] == "passed"
        and analysis["status"] == "passed"
        and replay["status"] == "passed"
        and replay_integrity
    )
    result = {
        "artifact_type": "can-log-lab",
        "status": "passed" if passed else "failed",
        "capture": capture,
        "analysis_summary": {
            "status": analysis["status"],
            "frame_count": analysis["frame_count"],
            "decoded_count": analysis["decoded_count"],
            "finding_count": analysis["finding_count"],
            "dbc_sha256": analysis["dbc_sha256"],
        },
        "replay": replay,
        "replay_integrity": replay_integrity,
        "artifacts": [
            str(log_path),
            str(output / "capture" / "capture.manifest.json"),
            str(output / "decode" / "decode-report.json"),
            str(output / "replay" / "replay-report.json"),
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "log-lab-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = [
        "# CAN Capture, Decode and Replay Lab",
        "",
        f"- Status: **{result['status']}**",
        f"- Captured frames: {capture['captured_count']}",
        f"- Decoded frames: {analysis['decoded_count']}",
        f"- Replay frames: {replay['sent_count']}",
        f"- Replay integrity: **{replay_integrity}**",
        f"- Log SHA-256: `{capture['log_sha256']}`",
        f"- DBC SHA-256: `{analysis['dbc_sha256']}`",
        "",
        "The raw can-utils log is the frame evidence. Decode and replay reports are derived evidence and can be regenerated.",
        "",
    ]
    (output / "log-lab-report.md").write_text("\n".join(markdown), encoding="utf-8")
    return result
