"""P30 adapter protocol and failure scenarios; synthetic service, no real LLM."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from explanation_fixture_service import fixture_service
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
CASES = {"normal": "passed", "invalid_reference": "refused", "value_drift": "refused",
         "manual_mismatch": "refused", "malformed": "refused", "truncation": "refused",
         "model_changed": "refused", "unavailable": "blocked", "timeout": "blocked",
         "unassessed": "unassessed", "manual_unapproved": "passed", "unsupported_prose": "passed"}


def run(output: Path, cli_python: Path | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Model scenario output must be absent")
    output = output.resolve()
    output.mkdir(parents=True)
    env = {**os.environ, "PYTHONUTF8": "1"}
    env.pop("PYTHONHOME", None)
    if cli_python:
        env.pop("PYTHONPATH", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    python = str(cli_python.absolute()) if cli_python else sys.executable
    commands = []

    def cli(label, arguments, code):
        proc = subprocess.run([python, "-m", "automotive_workbench.cli", *map(str, arguments)], cwd=output,
                              env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
        commands.append({"label": label, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        (output / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding="utf-8")
        if proc.returncode != code:
            raise ValueError(f"{label}: {proc.stdout} {proc.stderr}")
        return json.loads(proc.stdout)

    result = cli("project", ["run-project", ROOT / "examples/ecuc_diagnostic/integration.project.json", "--output", output / "project"], 3)
    report = Path(result["report_json"])
    schemas = [json.loads((ROOT / "schemas" / name).read_text()) for name in (
        "project-model-explanation.schema.json", "project-explanation-request.schema.json")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    validator = Draft202012Validator(schemas[0], registry=registry)
    cases = []
    with fixture_service() as (server, origin):
        for mode, status in CASES.items():
            server.mode, server.tags_count = mode, 0
            destination = output / mode
            result = cli(mode, ["explain-project", report, "--question", "为什么阻断？还缺什么证据？", "--output", destination,
                                "--model", "fixture:1", "--ollama-url", origin, "--knowledge-url", origin,
                                "--knowledge-query", "diagnostic timeout evidence", "--timeout", "0.05" if mode == "timeout" else "5"],
                         {"passed": 0, "refused": 2, "unassessed": 2, "blocked": 3}[status])
            validator.validate(result)
            if result["status"] != status or result["project_status"] != "blocked" or not result["fallback_facts"]:
                raise ValueError("Adapter overwrote original engineering status or lost fallback")
            if result["answer"] and result["answer"]["semantic_status"] != "unassessed":
                raise ValueError("Model prose was incorrectly certified")
            if mode == "manual_unapproved" and (result["answer"]["manual_quotes"] or not any(g["code"] == "KNOWLEDGE_UNAVAILABLE" for g in result["gaps"])):
                raise ValueError("Unapproved manual was accepted")
            cli("offline-replay", ["verify-model-explanation", report, destination], 0)
            cases.append({"case": mode, "status": status, "reason": result["reason"]})
    # Reverification works with services already stopped and without source checkout imports.
    cli("services-stopped", ["verify-model-explanation", report, output / "normal"], 0)
    summary = {"status": "passed", "evidence_kind": "synthetic-http-contract-fixture", "real_model_inference": False,
               "cases": cases, "model_semantic_quality": "unassessed"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
