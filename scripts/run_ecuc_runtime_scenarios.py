"""P29 same-run configuration/CAN links, fault harnesses and portable rejection evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "integration": "passed",
    "transmitter": "passed",
    "static-rejection": "failed",
    "wrong-mapping": "unassessed",
    "wrong-address": "unassessed",
    "timeout": "failed",
    "wrong-id": "failed",
    "backend-blocked": "blocked",
}
# These are explicit test harness faults, not target ECU observations. The real
# P20 virtual endpoints are used; wrong-ID send bypasses the peer filter on purpose.
DRIVER = """import sys
from unittest.mock import patch
from automotive_workbench import declared_communication as runner
from automotive_workbench.cli import main
fault = sys.argv.pop(1)
original = runner.open_bus
calls = []
def open_fault(config, filters):
    peer = len(calls) % 2 == 1
    bus = original(config, None if fault == "wrong-id" and peer else filters)
    calls.append(bus)
    if not peer:
        send = bus.send
        if fault == "timeout":
            bus.send = lambda *args, **kwargs: None
        elif fault == "wrong-id":
            def wrong(frame, *args, **kwargs):
                frame.arbitration_id += 1
                return send(frame, *args, **kwargs)
            bus.send = wrong
    return bus
with patch.object(runner, "open_bus", open_fault):
    raise SystemExit(main())
"""


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(output: Path, cli_python: Path | None = None) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Linked scenarios require absent output")
    output = output.resolve()
    output.mkdir(parents=True)
    source = output / "source"
    shutil.copytree(ROOT / "examples/ecuc_runtime", source)
    driver = output / "fault-driver.py"
    driver.write_text(DRIVER, encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1"}
    if cli_python:
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    python = str(cli_python.absolute()) if cli_python else sys.executable
    commands = []

    def cli(label: str, args: list[str], code: int = 0, fault: str = "") -> dict:
        prefix = (
            [python, str(driver), fault]
            if fault
            else [python, "-m", "automotive_workbench.cli"]
        )
        proc = subprocess.run(
            [*prefix, *args],
            cwd=output,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=180,
        )
        commands.append(
            {
                "label": label,
                "fault_harness": fault,
                "args": args,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        write(output / "commands.json", commands)
        if proc.returncode != code:
            raise ValueError(
                f"{label}: expected {code}, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            )
        return json.loads(proc.stdout)

    reports = {}
    for name, expected in CASES.items():
        kind = "transmitter" if name == "transmitter" else "integration"
        project = read(source / (kind + ".project.json"))
        candidate = source / (name + "-candidate")
        shutil.copytree(source / kind, candidate)
        project["inputs"]["candidate"] = {
            k: [x.replace(kind + "/", candidate.name + "/") for x in v]
            if isinstance(v, list)
            else v.replace(kind + "/", candidate.name + "/")
            for k, v in project["inputs"]["candidate"].items()
        }
        if name in {"static-rejection", "wrong-address"}:
            p = candidate / "modules.arxml"
            old, new = (
                ("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
                if name == "static-rejection"
                else ("<VALUE>256</VALUE>", "<VALUE>257</VALUE>")
            )
            text = p.read_text(encoding="utf-8")
            if old not in text:
                raise ValueError("Missing fixture mutation site")
            p.write_text(text.replace(old, new, 1), encoding="utf-8")
        if name == "wrong-mapping":
            project["runtime"]["bindings"][0]["signal"] = "NotTheSignal"
        path = source / (name + "-run.json")
        write(path, project)
        config = (
            ["--interface", "socketcan", "--channel", "missing-p29"]
            if name == "backend-blocked"
            else ["--channel", "p29-scenarios"]
        )
        destination = output / "portable/projects" / name
        result = cli(
            name,
            ["run-project", str(path), "--output", str(destination), *config],
            {"passed": 0, "failed": 2, "unassessed": 2, "blocked": 3}[expected],
            name if name in {"timeout", "wrong-id"} else "",
        )
        if result["status"] != expected or result["integrity_status"] != "passed":
            raise ValueError("Linked scenario status differs")
        reports[name] = destination / "bundle/project-report.json"
    # A second execution with identical declaration proves run identity changes.
    path = source / "integration-run.json"
    other = output / "portable/projects/second-run"
    cli(
        "second-run",
        [
            "run-project",
            str(path),
            "--output",
            str(other),
            "--channel",
            "p29-scenarios",
        ],
    )
    reports["second-run"] = other / "bundle/project-report.json"
    shutil.rmtree(source)
    (output / "portable").rename(output / "delivery")
    reports = {
        k: output / "delivery/projects" / k / "bundle/project-report.json"
        for k in reports
    }
    for name, path in reports.items():
        cli(name + "-verify", ["verify-ecuc-project", str(path)])
        if (
            cli(
                name + "-review",
                [
                    "run-project-review",
                    str(path),
                    "--output",
                    str(output / "delivery/reviews" / name),
                ],
            )["status"]
            != "answered"
        ):
            raise ValueError("Review refused verified linked evidence")
    for name, expected in [
        ("timeout", "regressed"),
        ("wrong-id", "regressed"),
        ("wrong-mapping", "not-comparable"),
        ("second-run", "stable"),
    ]:
        dest = output / "delivery/comparisons" / name
        result = cli(
            "compare-" + name,
            [
                "compare-projects",
                str(reports["integration"]),
                str(reports[name]),
                "--output",
                str(dest),
            ],
            0 if expected == "stable" else 2,
        )
        if result["status"] != expected:
            raise ValueError("Unexpected linked project comparison")
        cli(
            "verify-compare-" + name,
            ["verify-project-comparison", str(dest / "project-comparison.json")],
        )
    rejected = []
    for name in [
        "historical",
        "wrong-observation",
        "input-drift",
        "missing-runtime",
        "extra-record",
    ]:
        dest = output / "tampered" / name
        shutil.copytree(reports["second-run"].parent, dest)
        rawpath = dest / "runtime/declared-runtime-report.json"
        recordpath = dest / "runtime-link.json"
        record = read(recordpath)
        if name == "historical":
            rawpath.write_bytes(
                (
                    reports["integration"].parent
                    / "runtime/declared-runtime-report.json"
                ).read_bytes()
            )
        elif name == "wrong-observation":
            raw = read(rawpath)
            raw["vectors"]["value-tx"]["observed"]["frame_id"] += 1
            write(rawpath, raw)
        elif name == "input-drift":
            p = dest / "inputs/runtime-vectors.json"
            p.write_text(
                p.read_text(encoding="utf-8").replace("42", "43"), encoding="utf-8"
            )
        elif name == "missing-runtime":
            rawpath.unlink()
        else:
            record["extra"] = "unrecorded"
        if rawpath.exists():
            import hashlib

            record["runtime_sha256"] = hashlib.sha256(rawpath.read_bytes()).hexdigest()
        write(recordpath, record)
        cli(
            "reject-" + name,
            ["verify-ecuc-project", str(dest / "project-report.json")],
            1,
        )
        rejected.append(name)
    (output / "delivery").rename(output / "relocated")
    cli(
        "final-compare",
        [
            "verify-project-comparison",
            str(output / "relocated/comparisons/timeout/project-comparison.json"),
        ],
    )
    summary = {
        "status": "passed",
        "cases": CASES,
        "same_config_second_execution": True,
        "relocated_projects": len(reports),
        "reviews": len(reports),
        "rejections": rejected,
        "original_inputs_removed": True,
        "final_replay": "passed",
        "boundary": "CAN faults are explicit test harness injections; no independent or physical ECU evidence.",
    }
    write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cli-python", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cli_python), indent=2))
