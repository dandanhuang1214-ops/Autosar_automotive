"""P27 multi-project static acceptance, portable review/comparison and rejection evidence."""

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
    "task-gap": "failed",
    "communication-gap": "failed",
    "opaque": "unassessed",
    "missing-application": "unassessed",
    "ambiguous": "blocked",
    "historical": "passed",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(
    output: Path, cli_python: Path | None = None, object_policies: bool = False
) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("ECUC project scenarios require absent output")
    output = output.resolve()
    output.mkdir(parents=True)
    source = output / "source"
    shutil.copytree(ROOT / "examples/ecuc_acceptance", source)
    env = {**os.environ, "PYTHONUTF8": "1"}
    if cli_python:
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    interpreter = str(cli_python.absolute()) if cli_python else sys.executable
    commands = []

    def cli(label: str, args: list[str], code: int = 0) -> dict[str, Any]:
        proc = subprocess.run(
            [interpreter, "-m", "automotive_workbench.cli", *args],
            cwd=output,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=180,
        )
        record = {
            "label": label,
            "argv": args,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        commands.append(record)
        write(output / "commands.json", commands)
        if proc.returncode != code:
            raise ValueError(
                f"{label}: expected {code}, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            )
        return json.loads(proc.stdout)

    cases = dict(CASES)
    if object_policies:
        cases.update(
            {
                "signal-change": "failed",
                "task-change": "failed",
                "allowed-change": "passed",
                "unsupported-field": "unassessed",
                "missing-object": "failed",
                "policy-drift": "passed",
                "transmitter-change": "failed",
                "transmitter-allowed": "passed",
            }
        )
    reports = {}
    for name, expected in cases.items():
        kind = "transmitter" if name.startswith("transmitter") else "integration"
        project = read(
            source
            / (kind + (".protected" if object_policies else "") + ".project.json")
        )
        candidate = source / (name + "-candidate")
        shutil.copytree(source / kind, candidate)
        project["inputs"]["candidate"] = {
            k: (
                [x.replace(kind + "/", candidate.name + "/") for x in v]
                if isinstance(v, list)
                else v.replace(kind + "/", candidate.name + "/")
            )
            for k, v in project["inputs"]["candidate"].items()
        }
        mutation = {
            "signal-change": ("modules.arxml", "<VALUE>8</VALUE>", "<VALUE>12</VALUE>"),
            "transmitter-change": (
                "modules.arxml",
                "<VALUE>8</VALUE>",
                "<VALUE>12</VALUE>",
            ),
            "allowed-change": (
                "modules.arxml",
                "<VALUE>8</VALUE>",
                "<VALUE>12</VALUE>",
            ),
            "transmitter-allowed": (
                "modules.arxml",
                "<VALUE>8</VALUE>",
                "<VALUE>12</VALUE>",
            ),
            "task-change": (
                "modules.arxml",
                "/Demo/Os/TaskA</VALUE-REF>",
                "/Demo/Os/TaskB</VALUE-REF>",
            ),
            "task-gap": ("modules.arxml", "/Demo/Os/TaskA</VALUE-REF>", "</VALUE-REF>"),
            "communication-gap": (
                "modules.arxml",
                "/Demo/EcuC/C</VALUE-REF>",
                "/Demo/EcuC/Missing</VALUE-REF>",
            ),
            "opaque": (
                "modules.arxml",
                "<SHORT-NAME>ValueA</SHORT-NAME>",
                "<SHORT-NAME>ValueA</SHORT-NAME><VENDOR>changed</VENDOR>",
            ),
            "ambiguous": (
                "modules.arxml",
                "<SHORT-NAME>TaskB</SHORT-NAME>",
                "<SHORT-NAME>TaskA</SHORT-NAME>",
            ),
            "historical": (
                "tool.log",
                "Historical task binding failure",
                "New historical error observation",
            ),
        }.get(name)
        if mutation:
            file, old, new = mutation
            p = candidate / file
            p.write_text(
                p.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8"
            )
        if name == "missing-application":
            project["inputs"]["candidate"]["applications"] = []
        if object_policies and name in {"allowed-change", "transmitter-allowed"}:
            project["policies"] = [
                p for p in project["policies"] if p["id"] != "SIGNAL_SIZE"
            ]
            project["requirements"] = [
                r for r in project["requirements"] if r["id"] != "SIGNAL_SIZE"
            ]
        if object_policies and name == "unsupported-field":
            project["policies"][1]["definition"] = "/Synthetic/ComSignal/VendorUnknown"
        if object_policies and name == "missing-object":
            project["policies"][0]["object_id"] = "ecuc:/Demo/Com/Absent"
        if object_policies and name == "policy-drift":
            project["policies"][0]["object_id"] = "ecuc:/Demo/Com/PacketA"
        if name == "ambiguous" and object_policies:
            project["policies"] = [
                p for p in project["policies"] if p["id"] == "TASK_REF"
            ]
            project["requirements"] = [
                r for r in project["requirements"] if r["id"] in {"TASK_REF", "IMPACT"}
            ]
        if name == "ambiguous" and not object_policies:
            project["requirements"] = [
                x for x in project["requirements"] if x["id"] == "IMPACT"
            ]
        path = source / (name + "-run.json")
        write(path, project)
        destination = output / "portable" / "projects" / name
        result = cli(
            name,
            ["run-project", str(path), "--output", str(destination)],
            {"passed": 0, "failed": 2, "unassessed": 2, "blocked": 3}[expected],
        )
        if result["status"] != expected or result["integrity_status"] != "passed":
            raise ValueError(f"Unexpected {name} acceptance")
        reports[name] = destination / "bundle/project-report.json"
    # Neither original project declarations nor original ECUC inputs survive replay.
    shutil.rmtree(source)
    portable = output / "relocated"
    (output / "portable").rename(portable)
    reports = {
        name: portable / "projects" / name / "bundle/project-report.json"
        for name in reports
    }
    for name, path in reports.items():
        result = cli(name + "-replay", ["verify-ecuc-project", str(path)])
        if result["project_status"] != cases[name]:
            raise ValueError("Replay changed the recorded acceptance status")
        review = cli(
            name + "-review",
            [
                "run-project-review",
                str(path),
                "--output",
                str(portable / "reviews" / name),
            ],
        )
        if review["status"] != "answered":
            raise ValueError("Project review refused verified static evidence")
    comparison = portable / "comparison"
    result = cli(
        "compare",
        [
            "compare-projects",
            str(reports["integration"]),
            str(reports["communication-gap"]),
            "--output",
            str(comparison),
        ],
        2,
    )
    if result["status"] != "regressed":
        raise ValueError("Communication regression not exposed by project comparison")
    cli(
        "verify-compare",
        ["verify-project-comparison", str(comparison / "project-comparison.json")],
    )
    if object_policies:
        for label, other, expected, code in [
            ("signal-regression", "signal-change", "regressed", 2),
            ("task-regression", "task-change", "regressed", 2),
            ("policy-drift", "policy-drift", "not-comparable", 2),
        ]:
            directory = portable / label
            result = cli(
                label,
                [
                    "compare-projects",
                    str(reports["integration"]),
                    str(reports[other]),
                    "--output",
                    str(directory),
                ],
                code,
            )
            if result["status"] != expected:
                raise ValueError("Object policy comparison mismatch")
            cli(
                label + "-replay",
                [
                    "verify-project-comparison",
                    str(directory / "project-comparison.json"),
                ],
            )
    rejected = []
    for name in ("conclusion", "source", "policy", "inventory"):
        target = output / "tampered" / name
        shutil.copytree(reports["integration"].parent, target)
        if name == "conclusion":
            p = target / "project-report.json"
            data = read(p)
            data["status"] = "failed"
            write(p, data)
        elif name == "source":
            p = target / "ecuc/after/snapshot/project/modules.arxml"
            p.write_bytes(
                p.read_bytes().replace(b"<VALUE>8</VALUE>", b"<VALUE>12</VALUE>")
            )
        elif name == "policy":
            p = target / "inputs/project.json"
            data = read(p)
            data["requirements"][0]["expected"] = "unassessed"
            write(p, data)
        else:
            (target / "extra.txt").write_text("unexpected", encoding="utf-8")
        cli(
            "reject-" + name,
            ["verify-ecuc-project", str(target / "project-report.json")],
            1,
        )
        rejected.append(name)
    # Move the entire review/comparison tree again; relative references must survive.
    final = output / "delivery"
    portable.rename(final)
    cli(
        "final-project-replay",
        [
            "verify-ecuc-project",
            str(final / "projects/integration/bundle/project-report.json"),
        ],
    )
    cli(
        "final-comparison-replay",
        [
            "verify-project-comparison",
            str(final / "comparison/project-comparison.json"),
        ],
    )
    summary = {
        "status": "passed",
        "cases": cases,
        "relocated_projects": len(reports),
        "reviews": len(reports),
        "tamper_rejections": rejected,
        "comparison": "regressed",
        "original_inputs_removed": True,
        "final_replay": "passed",
    }
    write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cli-python", type=Path)
    parser.add_argument("--object-policies", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cli_python, args.object_policies), indent=2))
