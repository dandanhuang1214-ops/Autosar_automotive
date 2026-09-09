from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.applicability import build_runtime_applicability_profile
from automotive_workbench.can_backend import probe_can_backend
from automotive_workbench.can_io import (
    BusConfig,
    bus_isolation_evidence,
    exact_can_filters,
    open_bus,
)
from automotive_workbench.can_runtime import _command_receive, _python_can, _round_trip


def default_communication_config(interface: str = "virtual", channel: str | None = None) -> BusConfig:
    if channel:
        return BusConfig(interface, channel)
    if interface == "socketcan":
        return BusConfig(interface, "vcan0")
    return BusConfig(interface, f"workbench-communication-{uuid.uuid4()}")


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# CAN Communication Runtime Report",
        "",
        f"- Backend: `{result['backend']}`",
        f"- Channel: `{result['bus_config']['channel']}`",
        f"- Status: **{result['status']}**",
        f"- Reason: `{result['reason'] or 'none'}`",
        f"- Scenarios: {result['passed_count']}/{result['scenario_count']} passed",
        "",
        "| Scenario | Result | Expected | Observed |",
        "|---|---|---|---|",
    ]
    for scenario in result["scenarios"]:
        lines.append(
            f"| `{scenario['scenario']}` | {scenario['status']} | "
            f"{scenario['expected']} | {scenario['observed']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This report proves filtered application-level frame exchange on the selected python-can backend. It does not prove production ECUC generation, controller configuration, electrical CAN behavior, target timing, or target-hardware integration.",
            "",
        ]
    )
    return "\n".join(lines)


def run_communication_runtime(dbc: Path, config: BusConfig, output: Path) -> dict[str, Any]:
    started = time.perf_counter()
    backend = f"python-can {config.interface}"
    filters = exact_can_filters(0x100, 0x200)
    isolation = bus_isolation_evidence(config, filters)
    probe = probe_can_backend(config, output / "probe")
    scenarios: list[dict[str, Any]] = []
    reason = probe["reason"] if probe["status"] != "available" else ""
    status = "blocked" if reason else "passed"

    if not reason:
        local = None
        peer = None
        try:
            can = _python_can()
            database = _load_dbc(dbc)
            local = open_bus(config, filters)
            peer = open_bus(config, filters)
            scenarios = [
                _round_trip(database, local, peer, can),
                _command_receive(database, peer, local, can),
            ]
            if any(item["status"] != "passed" for item in scenarios):
                status = "failed"
                reason = "communication_scenario_failed"
        except Exception as exc:
            status = "failed"
            reason = "backend_runtime_failed"
            scenarios = [
                {
                    "scenario": "backend_runtime",
                    "status": "failed",
                    "expected": "selected backend completes bidirectional communication",
                    "observed": f"{type(exc).__name__}: {exc}",
                    "evidence": {"error_type": type(exc).__name__, "error": str(exc)},
                }
            ]
        finally:
            if local is not None:
                local.shutdown()
            if peer is not None:
                peer.shutdown()

    passed_count = sum(item["status"] == "passed" for item in scenarios)
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "can-communication-runtime",
        "schema_version": "can-communication-runtime-0.1",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "backend": backend,
        "bus_config": {
            "interface": config.interface,
            "channel": config.channel,
            "receive_own_messages": config.receive_own_messages,
            "fd": config.fd,
        },
        "applicability_profile": build_runtime_applicability_profile(
            variant=dbc.stem,
            software_version="communication-runtime-0.1",
            inputs=[dbc],
            backend=backend,
        ),
        "status": status,
        "reason": reason,
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "artifacts": [str(dbc)],
        "backend_probe": probe,
        "isolation": isolation,
        "scenarios": scenarios,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "can-runtime-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "can-runtime-report.md").write_text(
        _render_markdown(result), encoding="utf-8", newline="\n"
    )
    return result
