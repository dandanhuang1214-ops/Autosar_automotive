from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import validate_dbc_intent
from automotive_workbench.can_io import BusConfig
from automotive_workbench.communication_runtime import (
    default_communication_config,
    run_communication_runtime,
)
from automotive_workbench.domain import Finding


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finding(code: str, message: str, location: str) -> Finding:
    return Finding(
        code=code,
        severity="ERROR",
        message=message,
        source_artifact="can-runtime-report",
        kind="communication-path",
        field="runtime_binding",
        location=location,
    )


def bind_communication_evidence(
    static_validation: dict[str, Any],
    runtime_report_path: Path,
    dbc: Path,
    intent: Path,
) -> dict[str, Any]:
    runtime_report = json.loads(runtime_report_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    if static_validation.get("status") != "passed":
        findings.append(
            _finding(
                "COMMUNICATION-STATIC-VALIDATION-FAILED",
                "Static DBC-to-intent validation must pass before runtime binding",
                "static_validation",
            )
        )
    runtime_status = runtime_report.get("status")
    if runtime_status not in {"passed", "blocked"}:
        findings.append(
            _finding(
                "COMMUNICATION-RUNTIME-LAB-FAILED",
                "CAN runtime lab must pass before communication evidence is accepted",
                "runtime_report",
            )
        )

    observations: dict[tuple[str, str], dict[str, Any]] = {}
    for scenario in runtime_report.get("scenarios", []):
        if not isinstance(scenario, dict) or scenario.get("status") != "passed":
            continue
        evidence = scenario.get("evidence")
        if not isinstance(evidence, dict):
            continue
        message_name = evidence.get("message_name")
        decoded = evidence.get("decoded")
        if not isinstance(message_name, str) or not isinstance(decoded, dict):
            continue
        for signal_name, value in decoded.items():
            observations[(message_name, str(signal_name))] = {
                "scenario": scenario.get("scenario"),
                "direction": evidence.get("direction"),
                "frame_id": evidence.get("frame_id"),
                "payload_hex": evidence.get("payload_hex"),
                "decoded_value": value,
            }

    bindings: list[dict[str, Any]] = []
    for path in static_validation.get("communication_paths", []):
        message_name = str(path.get("dbc_message") or "")
        signal_name = str(path.get("dbc_signal") or "")
        identity = f"{message_name}.{signal_name}"
        observation = observations.get((message_name, signal_name))
        binding_findings: list[str] = []
        if observation is None:
            if runtime_status != "blocked":
                code = "COMMUNICATION-RUNTIME-EVIDENCE-MISSING"
                findings.append(_finding(code, f"No decoded runtime evidence for {identity}", identity))
                binding_findings.append(code)
        else:
            if observation["frame_id"] != path.get("frame_id"):
                code = "COMMUNICATION-FRAME-ID-MISMATCH"
                findings.append(
                    _finding(
                        code,
                        (
                            f"{identity} frame ID differs: static={path.get('frame_id')!r}, "
                            f"runtime={observation['frame_id']!r}"
                        ),
                        identity,
                    )
                )
                binding_findings.append(code)
            if observation["direction"] != path.get("direction"):
                code = "COMMUNICATION-DIRECTION-MISMATCH"
                findings.append(
                    _finding(
                        code,
                        (
                            f"{identity} direction differs: static={path.get('direction')!r}, "
                            f"runtime={observation['direction']!r}"
                        ),
                        identity,
                    )
                )
                binding_findings.append(code)

        binding_status = (
            "blocked"
            if runtime_status == "blocked" and observation is None
            else "bound" if not binding_findings else "failed"
        )
        bindings.append(
            {
                "identity": identity,
                "status": binding_status,
                "static_path": path,
                "runtime_observation": observation,
                "finding_codes": binding_findings,
            }
        )

    if not bindings:
        findings.append(
            _finding(
                "COMMUNICATION-STATIC-PATH-MISSING",
                "Static validation did not produce any communication paths",
                "static_validation.communication_paths",
            )
        )

    bound_count = sum(binding["status"] == "bound" for binding in bindings)
    timestamp = datetime.now(timezone.utc)
    result_status = "failed" if findings else (
        "blocked" if runtime_status == "blocked" else
        "passed" if bound_count == len(bindings) else "failed"
    )
    return {
        "artifact_type": "communication-chain-evidence",
        "schema_version": "communication-evidence-0.2",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": result_status,
        "reason": runtime_report.get("reason", ""),
        "local_ecu": bindings[0]["static_path"].get("local_ecu") if bindings else None,
        "source_artifacts": [
            {"artifact_type": "dbc", "source": str(dbc), "sha256": _sha256_file(dbc)},
            {"artifact_type": "bsw-intent", "source": str(intent), "sha256": _sha256_file(intent)},
            {
                "artifact_type": runtime_report.get("artifact_type", "can-runtime-report"),
                "source": str(runtime_report_path),
                "sha256": _sha256_file(runtime_report_path),
            },
        ],
        "static_validation_status": static_validation.get("status"),
        "runtime_status": runtime_status,
        "runtime_backend": runtime_report.get("backend"),
        "runtime_applicability_profile": runtime_report.get("applicability_profile"),
        "backend_probe": runtime_report.get("backend_probe"),
        "isolation": runtime_report.get("isolation"),
        "path_count": len(bindings),
        "bound_count": bound_count,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
        "bindings": bindings,
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Communication Chain Evidence",
        "",
        f"- Local ECU: `{result['local_ecu']}`",
        f"- Runtime backend: `{result['runtime_backend']}`",
        f"- Status: **{result['status']}**",
        f"- Bound paths: {result['bound_count']}/{result['path_count']}",
        "",
        "| Identity | Direction | Frame ID | Scenario | Result |",
        "|---|---|---:|---|---|",
    ]
    for binding in result["bindings"]:
        static = binding["static_path"]
        runtime = binding["runtime_observation"] or {}
        frame_id = static.get("frame_id")
        lines.append(
            f"| `{binding['identity']}` | `{static.get('direction')}` | "
            f"`0x{frame_id:X}` | `{runtime.get('scenario', '')}` | {binding['status']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This report binds explicit DBC/intent identities to filtered observations on the selected python-can backend. A blocked result records backend unavailability without treating it as a communication mismatch. It does not prove production ECUC generation, RTE behavior, controller configuration, electrical CAN behavior, or target-hardware integration.",
            "",
        ]
    )
    return "\n".join(lines)


def run_communication_chain(
    dbc: Path,
    intent: Path,
    output: Path,
    config: BusConfig | None = None,
) -> dict[str, Any]:
    static_validation = validate_dbc_intent(dbc, intent)
    runtime_output = output / "runtime"
    run_communication_runtime(
        dbc,
        config or default_communication_config(),
        runtime_output,
    )
    result = bind_communication_evidence(
        static_validation,
        runtime_output / "can-runtime-report.json",
        dbc,
        intent,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "static-validation.json").write_text(
        json.dumps(static_validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "communication-evidence-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "communication-evidence-report.md").write_text(
        _render_markdown(result), encoding="utf-8"
    )
    return result
