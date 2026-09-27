"""External execution CLI evidence: offline blocked/rejection or real OpenBSW."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from automotive_workbench.external_ecu import (  # noqa: E402
    read_json,
    write_json,
    verify_external_ecu,
    channel_lock,
)
from automotive_workbench.can_io import sha256_file  # noqa: E402


def offline_build(source: Path) -> Path:
    """Deliberately unavailable synthetic input, never an OpenBSW build claim."""
    evidence = source / "synthetic.txt"
    evidence.write_text(
        "Synthetic unavailable build fixture; no compiled ECU.\n", encoding="utf-8"
    )
    profile = read_json(ROOT / "examples/openbsw/read_cf01.json")
    record = {
        "schema_version": "external-ecu-build-0.1",
        "source_commit": "0" * 40,
        "preset": "synthetic-unavailable",
        "configuration": "test-only",
        "bindings": {
            "channel": "p23-absent",
            **{
                key: profile[key]
                for key in ("request_id", "response_id", "did", "expected_data_hex")
            },
        },
        "commands": [["synthetic-unavailable-fixture"]],
        "tools": {key: "not-run" for key in ("cmake", "compiler", "ninja")},
        "files": [
            {"role": role, "path": str(evidence), "sha256": sha256_file(evidence)}
            for role in (
                "cache",
                "can_source",
                "docan_source",
                "uds_source",
                "configure_log",
                "build_log",
            )
        ]
        + [
            {
                "role": "executable",
                "path": str(source / "absent.elf"),
                "sha256": "0" * 64,
            }
        ],
    }
    write_json(source / "build.json", record)
    return source / "build.json"


def run(output: Path, build_path: Path | None = None) -> dict:
    if output.exists():
        raise ValueError("Scenario output must be absent")
    output = output.resolve()
    source = output / "source"
    source.mkdir(parents=True)
    live = build_path is not None
    build_path = build_path.resolve() if build_path else offline_build(source)
    build = read_json(build_path)
    profile = read_json(ROOT / "examples/openbsw/read_cf01.json")
    spec = {
        "schema_version": "external-ecu-execution-0.1",
        "build": str(build_path),
        "profile": "profile.json",
        "channel": build["bindings"]["channel"],
        "startup_delay_s": 1.0,
        "shutdown_timeout_s": 1.0,
        "launch_ecu": True,
        "fault": "none",
    }
    results = {}
    cases = (
        ("normal", "no-response", "wrong-did", "wrong-response-id")
        if live
        else ("unavailable",)
    )
    for name in cases:
        variant, client = dict(spec), dict(profile)
        if name == "no-response":
            variant["launch_ecu"] = False
        if name == "wrong-did":
            variant["fault"], client["did"] = name, 0xCFFF
        if name == "wrong-response-id":
            variant["fault"], client["response_id"] = name, profile["response_id"] + 1
        write_json(source / "execution.json", variant)
        write_json(source / "profile.json", client)
        command = [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "run-external-ecu",
            str(source / "execution.json"),
            "--output",
            str(output / name),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=45)
        expected = 0 if name == "normal" else 3 if name == "unavailable" else 2
        if completed.returncode != expected:
            raise ValueError(
                f"{name}: {completed.returncode}: {completed.stdout} {completed.stderr}"
            )
        report = read_json(output / name / "external-ecu-report.json")
        if live:
            expected_reason = {
                "normal": "",
                "no-response": "timeout",
                "wrong-did": "negative_response",
                "wrong-response-id": "timeout",
            }[name]
            if report["reason"] != expected_reason or not all(
                item["reaped"] for item in report["cleanup"].values()
            ):
                raise ValueError(f"Unexpected scenario observation: {name}")
            if name == "normal":
                diagnostic = read_json(output / name / report["diagnostic"])
                if not {"SF", "FF", "FC", "CF"} <= {
                    frame["pci_type"] for frame in diagnostic["frames"]
                }:
                    raise ValueError("Missing actual multi-frame exchange")
        results[name] = {
            "status": report["status"],
            "reason": report["reason"],
            "report_sha256": sha256_file(output / name / "external-ecu-report.json"),
        }
    # Binding drift must fail before creating output, without a declared injection.
    write_json(source / "execution.json", spec)
    write_json(
        source / "profile.json", {**profile, "response_id": profile["response_id"] + 1}
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "run-external-ecu",
            str(source / "execution.json"),
            "--output",
            str(output / "rejected"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 1 or (output / "rejected").exists():
        raise ValueError("Undeclared binding drift was not rejected before output")
    write_json(
        output / "rejection.json",
        {
            "status": "passed",
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
        },
    )
    if live:
        write_json(source / "profile.json", profile)
        with channel_lock(spec["channel"]):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "automotive_workbench.cli",
                    "run-external-ecu",
                    str(source / "execution.json"),
                    "--output",
                    str(output / "lock-busy"),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        report = read_json(output / "lock-busy/external-ecu-report.json")
        if (
            completed.returncode != 3
            or report["reason"] != "channel_lock_busy"
            or report["ecu_pid"] is not None
        ):
            raise ValueError("Channel isolation failed")
        results["lock-busy"] = {
            "status": "blocked",
            "reason": report["reason"],
            "report_sha256": sha256_file(output / "lock-busy/external-ecu-report.json"),
        }
    shutil.rmtree(source)  # Only this script's generated variant inputs.
    relocated = output.with_name(output.name + "-relocated")
    if relocated.exists():
        raise ValueError("Relocation destination exists")
    output.rename(relocated)
    for name in results:
        verify_external_ecu(relocated / name / "external-ecu-report.json")
    summary = {
        "status": "passed",
        "evidence_kind": "real-openbsw-socketcan"
        if live
        else "synthetic-offline-rejection-only",
        "cases": results,
        "relocated_verified": len(results),
        "undeclared_drift_rejected": True,
    }
    write_json(relocated / "summary.json", summary)
    relocated.rename(output)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--build",
        type=Path,
        help="Use a real build record for Linux SocketCAN scenarios",
    )
    args = parser.parse_args()
    print(run(args.output, args.build))
