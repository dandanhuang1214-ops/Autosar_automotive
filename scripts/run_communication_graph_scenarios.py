"""Public P21 CLI scenarios; saves original inputs, conclusions and replay checks."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Scenario output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    checks = []

    def cli(
        name: str, command: str, projects: list[Path], expected: int
    ) -> dict[str, Any]:
        directory = output / name
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                command,
                *map(str, projects),
                "--output",
                str(directory),
            ],
            text=True,
            capture_output=True,
            cwd=ROOT,
        )
        if process.returncode != expected:
            raise RuntimeError(
                f"{name}: exit {process.returncode}: {process.stdout} {process.stderr}"
            )
        report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        replay = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "verify-communication-graph",
                str(directory / "report.json"),
            ],
            text=True,
            capture_output=True,
            cwd=ROOT,
        )
        if replay.returncode:
            raise RuntimeError(
                f"{name}: replay failed: {replay.stdout} {replay.stderr}"
            )
        (directory / "replay.json").write_text(replay.stdout, encoding="utf-8")
        checks.append(
            {
                "case": name,
                "exit_code": process.returncode,
                "status": report["status"],
                "replay": "passed",
            }
        )
        return report

    thermal = ROOT / "examples/thermal_control/project.json"
    window = ROOT / "examples/window_control/project-declared.json"
    for name, project in [("thermal", thermal), ("window", window)]:
        graph = cli(name, "build-communication-graph", [project], 0)
        if {n["direction"] for n in graph["nodes"]} != {"tx", "rx"}:
            raise RuntimeError("Missing Tx/Rx coverage")
    stable = cli("stable", "compare-communication-config", [thermal, thermal], 0)
    if stable["affected"] or stable["requirements"]:
        raise RuntimeError("Unchanged configuration must not trigger reruns")
    cli("different-project", "compare-communication-config", [thermal, window], 2)
    candidate = output / "inputs" / "scale"
    shutil.copytree(thermal.parent, candidate)
    dbc = candidate / "thermal_control.dbc"
    dbc.write_text(
        dbc.read_text(encoding="utf-8").replace("(0.1,-40)", "(0.2,-40)", 1),
        encoding="utf-8",
    )
    impact = cli(
        "scale-impact",
        "compare-communication-config",
        [thermal, candidate / "project.json"],
        0,
    )
    if (
        impact["vectors"] != ["thermal-status"]
        or "thermal-status" not in impact["requirements"]
        or "pump-status" in impact["requirements"]
    ):
        raise RuntimeError(
            "Impact must identify ThermalStatus and its acceptance items"
        )
    mutations = {
        "missing-reference": (
            "GRAPH-MISSING-REFERENCE",
            lambda p: p["signals"][0].update(i_pdu="Absent"),
        ),
        "duplicate-identity": (
            "GRAPH-DUPLICATE-IDENTITY",
            lambda p: p["signals"][1].update(com_signal=p["signals"][0]["com_signal"]),
        ),
        "direction-conflict": (
            "GRAPH-DIRECTION",
            lambda p: p["signals"][0].update(direction="rx"),
        ),
        "length-conflict": (
            "GRAPH-LENGTH-LAYOUT",
            lambda p: p["messages"][0].update(dlc=1),
        ),
        "route-endpoint": (
            "GRAPH-ROUTE-ENDPOINT",
            lambda p: p["signals"][0].update(canif_pdu=p["messages"][1]["canif_pdu"]),
        ),
    }
    for name, (code, mutate) in mutations.items():
        folder = output / "inputs" / name
        shutil.copytree(thermal.parent, folder)
        path = folder / "bsw_intent.json"
        intent = json.loads(path.read_text(encoding="utf-8"))
        mutate(intent)
        path.write_text(json.dumps(intent, indent=2) + "\n", encoding="utf-8")
        report = cli(name, "build-communication-graph", [folder / "project.json"], 2)
        if code not in {f["code"] for f in report["findings"]}:
            raise RuntimeError(f"Missing expected rule {code}")
    migrated = output / "migrated-impact.json"
    shutil.copyfile(output / "scale-impact/report.json", migrated)
    shutil.rmtree(candidate)  # generated fixture only: prove source-independent replay
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "verify-communication-graph",
            str(migrated),
        ],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if verify.returncode:
        raise RuntimeError(verify.stdout)
    (output / "migration-replay.json").write_text(verify.stdout, encoding="utf-8")
    summary = {"status": "passed", "checks": checks, "migration_replay": "passed"}
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output.resolve()), indent=2))
