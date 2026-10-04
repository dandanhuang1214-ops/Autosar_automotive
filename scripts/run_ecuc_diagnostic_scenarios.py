"""P29 diagnostic dependencies: real P23 runner, portable offline/live scenarios."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(
    output: Path, cli_python: Path | None = None, build: Path | None = None
) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Diagnostic scenarios require absent output")
    output = output.resolve()
    source = output / "source"
    shutil.copytree(ROOT / "examples/ecuc_diagnostic", source)
    env = {**os.environ, "PYTHONUTF8": "1"}
    if cli_python:
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    python = str(cli_python.absolute()) if cli_python else sys.executable
    commands: list[dict] = []

    def cli(label: str, args: list[str], code: int = 0) -> dict:
        proc = subprocess.run(
            [python, "-m", "automotive_workbench.cli", *args],
            cwd=output,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        commands.append(
            {
                "label": label,
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

    if build:
        definition = read(build)
        for item in definition["files"]:
            item["path"] = str((build.parent / item["path"]).resolve())
        write(source / "build.json", definition)
        spec = read(source / "execution.json")
        spec["channel"] = definition["bindings"]["channel"]
        write(source / "execution.json", spec)
        profile = read(source / "profile.json")
        profile.update(
            {k: v for k, v in definition["bindings"].items() if k != "channel"}
        )
        write(source / "profile.json", profile)
        for kind in ["integration", "transmitter"]:
            p = source / (kind + ".project.json")
            d = read(p)
            d["diagnostic"]["identity"] = {
                "source_commit": definition["source_commit"],
                **definition["bindings"],
            }
            write(p, d)
    normal = "passed" if build else "blocked"
    cases = {
        "integration": normal,
        "transmitter": normal,
        "repeat": normal,
        "static-rejection": "failed",
        "identity-mismatch": "unassessed",
        "semantic-unassessed": "unassessed",
        "backend-blocked": "blocked",
    }
    if build:
        cases.update(
            {
                "no-response": "failed",
                "wrong-did": "failed",
                "wrong-response-id": "failed",
            }
        )
    reports = {}
    original_spec, original_profile = (
        read(source / "execution.json"),
        read(source / "profile.json"),
    )
    for name, expected in cases.items():
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
        spec, profile = dict(original_spec), dict(original_profile)
        if name == "static-rejection":
            p = candidate / "modules.arxml"
            old = p.read_text(encoding="utf-8")
            new = old.replace("<VALUE>8</VALUE>", "<VALUE>12</VALUE>", 1)
            if old == new:
                raise ValueError("Mutation site missing")
            p.write_text(new, encoding="utf-8")
        if name == "identity-mismatch":
            project["diagnostic"]["identity"]["did"] += 1
        if name == "semantic-unassessed":
            project["diagnostic"]["relation"] = "configuration-semantic"
        if name == "no-response":
            spec["launch_ecu"] = False
        if name == "wrong-did":
            spec["fault"] = name
            profile["did"] = 0xCFFF
        if name == "wrong-response-id":
            spec["fault"] = name
            profile["response_id"] += 1
        write(source / "execution.json", spec)
        write(source / "profile.json", profile)
        path = source / (name + "-run.json")
        write(path, project)
        dest = output / "portable/projects" / name
        result = cli(
            name,
            [
                "run-project",
                str(path),
                "--output",
                str(dest),
                "--interface",
                "virtual" if name == "backend-blocked" else "socketcan",
                "--channel",
                spec["channel"],
            ],
            {"passed": 0, "failed": 2, "unassessed": 2, "blocked": 3}[expected],
        )
        if result["status"] != expected or result["integrity_status"] != "passed":
            raise ValueError("Unexpected project outcome")
        report = dest / "bundle/project-report.json"
        check = read(dest / "bundle/ecuc-stage.json")["checks"][
            "diagnostic.read-version"
        ]
        if (
            name
            in {
                "static-rejection",
                "identity-mismatch",
                "semantic-unassessed",
                "backend-blocked",
            }
            and (dest / "bundle/external-ecu").exists()
        ):
            raise ValueError("Preflight rejection executed ECU")
        if name in {"no-response", "wrong-did", "wrong-response-id"} and check[
            "reason"
        ] != ("negative_response" if name == "wrong-did" else "timeout"):
            raise ValueError("Unexpected live fault reason")
        reports[name] = report
    # The original inputs are now gone. Every review and replay must use snapshots.
    shutil.rmtree(source)
    for name, path in reports.items():
        cli("verify-" + name, ["verify-ecuc-project", str(path)])
        result = cli(
            "review-" + name,
            [
                "run-project-review",
                str(path),
                "--output",
                str(output / "portable/reviews" / name),
            ],
        )
        if result["status"] != "answered":
            raise ValueError("Review failed")
    for name, target, expected in [
        ("repeat", "repeat", "stable"),
        ("identity", "identity-mismatch", "not-comparable"),
        ("static", "static-rejection", "regressed" if build else "changed"),
    ]:
        result = cli(
            "compare-" + name,
            [
                "compare-projects",
                str(reports["integration"]),
                str(reports[target]),
                "--output",
                str(output / "portable/comparisons" / name),
            ],
            2 if expected != "stable" else 0,
        )
        if result["status"] != expected:
            raise ValueError("Unexpected comparison")
    rejects = []
    rejection_cases = ["historical", "missing", "input-drift", "context", "extra"] + (
        ["historical-client", "wrong-payload"] if build else []
    )
    for name in rejection_cases:
        dest = output / "rejected" / name
        shutil.copytree(reports["repeat"].parent, dest)
        if name == "historical":
            shutil.rmtree(dest / "external-ecu")
            shutil.copytree(
                reports["integration"].parent / "external-ecu", dest / "external-ecu"
            )
            import hashlib

            p = dest / "diagnostic-link.json"
            data = read(p)
            data["runtime_sha256"] = hashlib.sha256(
                (dest / data["runtime_path"]).read_bytes()
            ).hexdigest()
            write(p, data)
        if name in {"historical-client", "wrong-payload"}:
            import hashlib

            diagnostic = dest / "external-ecu/diagnostic"
            if name == "historical-client":
                shutil.rmtree(diagnostic)
                shutil.copytree(
                    reports["integration"].parent / "external-ecu/diagnostic",
                    diagnostic,
                )
            else:
                p = diagnostic / "uds-did-report.json"
                data = read(p)
                data["response_payload_hex"] = "62CFFF00"
                write(p, data)
            p = dest / "external-ecu/external-ecu-report.json"
            data = read(p)
            for item in data["inventory"]:
                item["sha256"] = hashlib.sha256(
                    (p.parent / item["path"]).read_bytes()
                ).hexdigest()
            write(p, data)
            link = dest / "diagnostic-link.json"
            data = read(link)
            data["runtime_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            write(link, data)
        if name == "missing":
            (dest / "external-ecu/external-ecu-report.json").unlink()
        if name == "input-drift":
            p = dest / "inputs/runner-profile.json"
            data = read(p)
            data["did"] += 1
            write(p, data)
        if name == "context":
            p = dest / "diagnostic-link.json"
            data = read(p)
            data["context"]["candidate_sha256"] = "a" * 64
            write(p, data)
        if name == "extra":
            (dest / "inputs/extra.txt").write_text("unexpected", encoding="utf-8")
        cli(
            "reject-" + name,
            ["verify-ecuc-project", str(dest / "project-report.json")],
            1,
        )
        rejects.append(name)
    (output / "portable").rename(output / "relocated")
    for name in cases:
        cli(
            "relocated-" + name,
            [
                "verify-ecuc-project",
                str(
                    output / "relocated/projects" / name / "bundle/project-report.json"
                ),
            ],
        )
    for name in ["repeat", "identity", "static"]:
        cli(
            "relocated-comparison-" + name,
            [
                "verify-project-comparison",
                str(
                    output / "relocated/comparisons" / name / "project-comparison.json"
                ),
            ],
        )
    summary = {
        "status": "passed",
        "mode": "independent-openbsw-socketcan"
        if build
        else "offline-blocked-and-rejection-only",
        "cases": cases,
        "relocated_verified": len(cases),
        "reviews": len(cases),
        "rejected": rejects,
        "boundary": "Explicit acceptance dependency; no generated-code mapping or physical ECU claim.",
    }
    write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cli-python", type=Path)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cli_python, args.build), indent=2))
