"""P30 fact gate: CLI, two project shapes, relocation and strict rejection."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(output: Path, cli_python: Path | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Scenario output must be absent")
    output = output.resolve()
    source = output / "source"
    shutil.copytree(ROOT / "examples/ecuc_diagnostic", source)
    env = {**os.environ, "PYTHONUTF8": "1"}
    env.pop("PYTHONHOME", None)
    if cli_python:
        env.pop("PYTHONPATH", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    python = str(cli_python.absolute()) if cli_python else sys.executable
    commands = []

    def cli(label, arguments, expected=0):
        proc = subprocess.run([python, "-m", "automotive_workbench.cli", *map(str, arguments)],
                              cwd=output, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=180)
        commands.append({"label": label, "arguments": list(map(str, arguments)),
                         "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        write(output / "commands.json", commands)
        if proc.returncode != expected:
            raise ValueError(f"{label}: {proc.stdout} {proc.stderr}")
        return json.loads(proc.stdout)

    cases = []
    for name in ("integration", "transmitter"):
        result = cli(name, ["run-project", source / f"{name}.project.json", "--output", output / name], 3)
        report = Path(result["report_json"])
        request_path = output / f"{name}-request.json"
        cli("prepare", ["prepare-project-explanation", report, "--question", "哪些项目证据记录了阻断？", "--output", request_path])
        request = json.loads(request_path.read_text(encoding="utf-8"))
        fact = request["facts"][0]
        answer = {"schema_version": "project-explanation-answer-0.1", "request_id": request["request_id"],
                  "status": "selected", "claims": [{"fact_id": fact["fact_id"], "value": fact["value"]}]}
        answer_path = output / f"{name}-answer.json"
        write(answer_path, answer)
        valid = cli("valid", ["validate-project-explanation", report, request_path, answer_path])
        if valid["project_status"] != "blocked" or valid["facts"][0]["value"] != "blocked":
            raise ValueError("Project status was not preserved")
        variants = []
        for field, value in (("fact_id", "0" * 64), ("value", "passed")):
            bad = copy.deepcopy(answer)
            bad["claims"][0][field] = value
            variants.append(bad)
        variants += [{**answer, "text": "All physical ECU tests passed"},
                     {**answer, "request_id": "0" * 64}]
        for index, bad in enumerate(variants):
            bad_path = output / f"{name}-rejected-{index}.json"
            write(bad_path, bad)
            cli("reject", ["validate-project-explanation", report, request_path, bad_path], 1)
        unknown = output / f"{name}-unassessed.json"
        write(unknown, {**answer, "status": "unassessed", "claims": []})
        cli("unassessed", ["validate-project-explanation", report, request_path, unknown])
        moved = output / f"搬移 {name}"
        shutil.move(str(report.parent), moved)
        report = moved / report.name
        cli("relocated", ["validate-project-explanation", report, request_path, answer_path])
        cases.append({"name": name, "fact_count": len(request["facts"]), "rejected": len(variants)})
    shutil.rmtree(source)
    for name in ("integration", "transmitter"):
        cli("source-removed", ["validate-project-explanation", output / f"搬移 {name}/project-report.json",
                               output / f"{name}-request.json", output / f"{name}-answer.json"])
    summary = {"status": "passed", "cases": cases,
               "boundary": "Exact fact gate only; no model or free-text correctness assessment."}
    write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))
