"""A single read-only DID request to an independently running ECU."""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import (
    BusConfig,
    bus_isolation_evidence,
    exact_can_filters,
    open_bus,
    sha256_file,
)
from automotive_workbench.uds_runtime import _diag_libs, probe_uds_backend


def load_did_profile(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    profile = json.loads(raw.decode("utf-8-sig"))
    keys = {
        "schema_version",
        "target",
        "request_id",
        "response_id",
        "did",
        "expected_data_hex",
        "timeout_s",
    }
    if not isinstance(profile, dict) or set(profile) != keys:
        raise ValueError("DID profile must use the closed uds-did-profile schema")
    if profile["schema_version"] != "uds-did-profile-0.1":
        raise ValueError("Unsupported DID profile schema_version")
    if not isinstance(profile["target"], str) or not profile["target"].strip():
        raise ValueError("DID profile requires target")
    for key, maximum in (
        ("request_id", 0x7FF),
        ("response_id", 0x7FF),
        ("did", 0xFFFF),
    ):
        if type(profile[key]) is not int or not 0 <= profile[key] <= maximum:
            raise ValueError(f"DID profile {key} must be an integer in 0..{maximum}")
    if profile["request_id"] == profile["response_id"]:
        raise ValueError("DID profile request_id and response_id must differ")
    expected = profile["expected_data_hex"]
    if not isinstance(expected, str) or not re.fullmatch(
        r"(?:[0-9A-F]{2}){1,4092}", expected
    ):
        raise ValueError(
            "DID profile expected_data_hex requires 1..4092 uppercase hex bytes"
        )
    timeout = profile["timeout_s"]
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0.05 <= timeout <= 30
    ):
        raise ValueError("DID profile timeout_s must be finite and in 0.05..30")
    return profile, hashlib.sha256(raw).hexdigest()


def read_uds_did(profile_path: Path, config: BusConfig, output: Path) -> dict[str, Any]:
    """Send only SID 0x22; never start a responder or change ECU sessions/state."""
    profile, profile_hash = load_did_profile(profile_path)
    if config.interface not in {"virtual", "socketcan"} or config.fd:
        raise ValueError("DID client supports classic CAN virtual/socketcan only")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("DID client output must be an empty directory")
    output.mkdir(parents=True, exist_ok=True)
    request_id, response_id = profile["request_id"], profile["response_id"]
    filters = exact_can_filters(request_id, response_id)
    probe = probe_uds_backend(config)
    result: dict[str, Any] = {
        "artifact_type": "uds-did-read",
        "schema_version": "uds-did-read-0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "reason": probe["reason"],
        "target": profile["target"],
        "target_identity_verified": False,
        "profile": {"source": str(profile_path.resolve()), "sha256": profile_hash},
        "bus_config": asdict(config),
        "probe": probe,
        "isolation": bus_isolation_evidence(config, filters),
        "request_payload_hex": f"22{profile['did']:04X}",
        "response_payload_hex": "",
        "expected_data_hex": profile["expected_data_hex"],
        "actual_data_hex": "",
        "negative_response_code": None,
        "transport_errors": [],
        "frames": [],
        "dropped_frame_count": 0,
        "capture": None,
    }
    if probe["status"] == "available":
        _exchange(profile, config, output, result)
    result["source_artifacts"] = [result["profile"]]
    if result["capture"] is not None:
        result["source_artifacts"].append(result["capture"])
    (output / "uds-did-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# UDS DID Read",
        "",
        f"- Target (declared): `{profile['target']}`",
        f"- Status: `{result['status']}`",
        f"- Reason: `{result['reason'] or 'none'}`",
        f"- Request: `{result['request_payload_hex']}`",
        f"- Response: `{result['response_payload_hex']}`",
        f"- Expected data: `{result['expected_data_hex']}`",
        f"- Actual data: `{result['actual_data_hex']}`",
        "",
        "| Direction | CAN ID | ISO-TP frame | Data |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| {f['direction']} | {f['can_id_hex']} | {f['pci_type']} | {f['data_hex']} |"
        for f in result["frames"]
    )
    lines.extend(
        [
            "",
            "Only one ReadDataByIdentifier request is sent. No responder is started.",
            "A matching value does not authenticate the ECU or prove production behavior.",
            "Timeout alone does not identify a faulty BSW module.",
            "",
        ]
    )
    (output / "uds-did-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def _exchange(
    profile: dict[str, Any], config: BusConfig, output: Path, result: dict[str, Any]
) -> None:
    can, isotp, _, client_cls, connection_cls = _diag_libs()
    from udsoncan.exceptions import (
        InvalidResponseException,
        NegativeResponseException,
        TimeoutException,
        UnexpectedResponseException,
    )

    messages: list[Any] = []
    guard = threading.Lock()

    def record(message: Any) -> None:
        with guard:
            if len(messages) < 1024:
                messages.append(message)
            else:
                result["dropped_frame_count"] += 1

    def transport_error(error: Exception) -> None:
        with guard:
            if len(result["transport_errors"]) < 32:
                result["transport_errors"].append(type(error).__name__)

    result.update(status="failed", reason="timeout")
    try:
        with ExitStack() as resources:
            monitor = open_bus(
                config, exact_can_filters(profile["request_id"], profile["response_id"])
            )
            resources.callback(monitor.shutdown)
            monitor_notifier = can.Notifier(monitor, [record], timeout=0.02)
            resources.callback(monitor_notifier.stop)
            bus = open_bus(config, exact_can_filters(profile["response_id"]))
            resources.callback(bus.shutdown)
            notifier = can.Notifier(bus, [], timeout=0.02)
            resources.callback(notifier.stop)
            stack = isotp.NotifierBasedCanStack(
                bus,
                notifier,
                address=isotp.Address(
                    isotp.AddressingMode.Normal_11bits,
                    txid=profile["request_id"],
                    rxid=profile["response_id"],
                ),
                params={
                    "tx_data_length": 8,
                    "tx_padding": 0,
                    "blocksize": 8,
                    "stmin": 0,
                },
                error_handler=transport_error,
            )
            resources.callback(stack.stop)
            connection = connection_cls(stack)
            client_config = {
                "data_identifiers": {
                    profile["did"]: f"{len(profile['expected_data_hex']) // 2}s"
                },
                "request_timeout": profile["timeout_s"],
                "p2_timeout": profile["timeout_s"],
                "p2_star_timeout": profile["timeout_s"],
                "tolerate_zero_padding": False,
            }
            with client_cls(connection, config=client_config) as client:
                response = client.read_data_by_identifier(profile["did"])
                result["response_payload_hex"] = response.original_payload.hex().upper()
                result["actual_data_hex"] = (
                    response.service_data.values[profile["did"]][0].hex().upper()
                )
                matched = result["actual_data_hex"] == profile["expected_data_hex"]
                result.update(
                    status="passed" if matched else "failed",
                    reason="" if matched else "data_mismatch",
                )
    except NegativeResponseException as exc:
        result.update(
            reason="negative_response", negative_response_code=exc.response.code
        )
        result["response_payload_hex"] = (
            (exc.response.original_payload or b"").hex().upper()
        )
    except (InvalidResponseException, UnexpectedResponseException) as exc:
        result["reason"] = (
            "invalid_response"
            if isinstance(exc, InvalidResponseException)
            else "unexpected_response"
        )
        result["response_payload_hex"] = (
            (exc.response.original_payload or b"").hex().upper()
        )
    except TimeoutException:
        result["reason"] = "timeout"
    except (can.CanError, OSError) as exc:
        result.update(status="blocked", reason="backend_io_error")
        result["transport_errors"].append(type(exc).__name__)

    frames = []
    for message in messages:
        data = bytes(message.data)
        valid = not (
            message.is_error_frame
            or message.is_remote_frame
            or message.is_extended_id
            or message.is_fd
        )
        pci = (
            {0: "SF", 1: "FF", 2: "CF", 3: "FC"}.get(data[0] >> 4, "unknown")
            if data and valid
            else "unknown"
        )
        frames.append(
            {
                "timestamp": message.timestamp,
                "direction": "request"
                if message.arbitration_id == profile["request_id"]
                else "response",
                "can_id_hex": f"0x{message.arbitration_id:03X}",
                "pci_type": pci,
                "data_hex": data.hex().upper(),
            }
        )
    result["frames"] = frames
    if result["status"] == "passed" and (
        result["dropped_frame_count"] or result["transport_errors"]
    ):
        result.update(status="failed", reason="transport_evidence_incomplete")
    log_path = output / "uds-did.log"
    writer = can.Logger(str(log_path))
    try:
        for message in messages:
            writer.on_message_received(message)
    finally:
        writer.stop()
    result["capture"] = {
        "source": str(log_path.resolve()),
        "sha256": sha256_file(log_path),
    }
