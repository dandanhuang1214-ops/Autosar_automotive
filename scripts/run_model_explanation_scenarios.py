"""P30 adapter protocol and failure scenarios; synthetic service, no real LLM."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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
    agent_retrieval = None
    agent_trace = None
    agent_checkpoint = None
    agent_resume = None
    agent_evaluation = None
    agent_evaluation_manifest = None
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
        server.mode = "normal"
        agent_retrieval = cli(
            "agent-knowledge-policy",
            ["retrieve-agent-knowledge", ROOT / "examples/knowledge/agent-read-policy.json",
             "--query", "diagnostic timeout evidence", "--knowledge-url", origin,
             "--timeout", "5"],
            0,
        )
        retrieval_schema = json.loads(
            (ROOT / "schemas/agent-knowledge-retrieval.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(retrieval_schema).validate(agent_retrieval)
        (output / "agent-knowledge-retrieval.json").write_text(
            json.dumps(agent_retrieval, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        server.mode, server.tags_count = "agent", 0
        agent_trace = cli(
            "readonly-agent",
            ["run-readonly-agent", report, "--goal", "核对项目阻断状态及资料边界",
             "--model", "fixture:1", "--output", output / "readonly-agent-trace.json",
             "--ollama-url", origin, "--knowledge-url", origin,
             "--knowledge-policy", ROOT / "examples/knowledge/agent-read-policy.json",
             "--timeout", "5"],
            0,
        )
        agent_schema = json.loads(
            (ROOT / "schemas/readonly-agent-trace.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(agent_schema).validate(agent_trace)
        if (
            agent_trace["status"] != "passed"
            or agent_trace["semantic_status"] != "unassessed"
            or agent_trace["usage"]["model_calls"] != 4
            or agent_trace["usage"]["tool_calls"] != 3
        ):
            raise ValueError("Read-only Agent fixture did not complete its bounded loop")
        server.mode, server.tags_count = "agent", 0
        checkpoint_path = output / "readonly-agent-checkpoint.json"
        agent_checkpoint = cli(
            "readonly-agent-pause",
            ["run-readonly-agent", report, "--goal", "核对项目阻断状态及资料边界",
             "--model", "fixture:1", "--output", checkpoint_path,
             "--ollama-url", origin, "--knowledge-url", origin,
             "--knowledge-policy", ROOT / "examples/knowledge/agent-read-policy.json",
             "--pause-after-tool-calls", "1", "--timeout", "5"],
            0,
        )
        if agent_checkpoint["status"] != "paused":
            raise ValueError("Read-only Agent did not pause at the requested boundary")
        cli("readonly-agent-checkpoint-offline", [
            "verify-readonly-agent-checkpoint", checkpoint_path], 0)
        resume_path = output / "readonly-agent-resume.json"
        agent_resume = cli(
            "readonly-agent-resume",
            ["resume-readonly-agent", report, checkpoint_path, "--output", resume_path,
             "--ollama-url", origin, "--knowledge-url", origin,
             "--knowledge-policy", ROOT / "examples/knowledge/agent-read-policy.json",
             "--timeout", "5"],
            0,
        )
        if (
            agent_resume["status"] != "passed"
            or agent_resume["outcome_kind"] != "trace"
        ):
            raise ValueError("Read-only Agent checkpoint did not resume to completion")
        server.mode = "unavailable"
        retried = cli(
            "readonly-agent-resume-idempotent-retry",
            ["resume-readonly-agent", report, checkpoint_path, "--output", resume_path,
             "--ollama-url", origin, "--knowledge-url", origin,
             "--knowledge-policy", ROOT / "examples/knowledge/agent-read-policy.json",
             "--timeout", "5"],
            0,
        )
        if retried != agent_resume:
            raise ValueError("Completed Agent resume retry changed its saved result")
        policy_name = "agent-read-policy.json"
        shutil.copy2(ROOT / "examples/knowledge/agent-read-policy.json", output / policy_name)
        evaluation_spec = {
            "evaluation_id": "synthetic-readonly-agent-contract",
            "split": "held-out",
            "formation": "Synthetic protocol case; never a model-quality claim.",
            "cases": [
                {
                    "case_id": "bounded-three-tool-loop",
                    "category": "synthetic-contract",
                    "report": "project/bundle/project-report.json",
                    "goal": "核对项目阻断状态及资料边界",
                    "expected": {
                        "status": "passed",
                        "reason_prefix": "completed_with_unassessed_model_summary",
                        "first_tool": "project_verify_report",
                        "required_tools": [
                            "project_verify_report",
                            "project_query_facts",
                            "knowledge_retrieve_reviewed",
                        ],
                        "forbidden_tools": [],
                        "required_evidence_tools": [
                            "project_verify_report",
                            "project_query_facts",
                            "knowledge_retrieve_reviewed",
                        ],
                        "gold_facts": [
                            {
                                "artifact_id": "stage-ecuc",
                                "pointer": "/checks/diagnostic.read-version/status",
                                "value": "blocked",
                            },
                            {
                                "artifact_id": "stage-ecuc",
                                "pointer": "/checks/diagnostic.read-version/reason",
                                "value": "diagnostic_backend_mismatch",
                            },
                        ],
                        "knowledge_document_ids": [1],
                        "max_model_calls": 4,
                        "max_tool_calls": 3,
                        "max_total_tokens": 4096,
                    },
                }
            ],
        }
        spec_path = output / "readonly-agent-eval-spec.json"
        spec_path.write_text(
            json.dumps(evaluation_spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "readonly-agent-eval-manifest.json"
        agent_evaluation_manifest = cli(
            "freeze-readonly-agent-evaluation",
            [
                "freeze-readonly-agent-eval",
                spec_path,
                "--root",
                output,
                "--implementation-root",
                ROOT,
                "--output",
                manifest_path,
                "--model",
                "fixture:1",
                "--model-digest",
                "a" * 64,
                "--knowledge-policy",
                policy_name,
            ],
            0,
        )
        server.mode, server.tags_count = "agent", 0
        agent_evaluation = cli(
            "run-readonly-agent-evaluation",
            [
                "run-readonly-agent-eval",
                manifest_path,
                "--root",
                output,
                "--implementation-root",
                ROOT,
                "--manifest-id",
                agent_evaluation_manifest["manifest_id"],
                "--output",
                output / "readonly-agent-evaluation",
                "--ollama-url",
                origin,
                "--knowledge-url",
                origin,
                "--timeout",
                "5",
            ],
            0,
        )
        if agent_evaluation["status"] != "passed":
            raise ValueError("Synthetic read-only Agent evaluation did not pass")
    # Reverification works with services already stopped and without source checkout imports.
    cli("services-stopped", ["verify-model-explanation", report, output / "normal"], 0)
    agent_verification = cli(
        "readonly-agent-services-stopped",
        ["verify-readonly-agent-trace", output / "readonly-agent-trace.json"],
        0,
    )
    checkpoint_verification = cli(
        "readonly-agent-checkpoint-services-stopped",
        ["verify-readonly-agent-checkpoint", output / "readonly-agent-checkpoint.json"],
        0,
    )
    resume_verification = cli(
        "readonly-agent-resume-services-stopped",
        ["verify-readonly-agent-resume", output / "readonly-agent-checkpoint.json",
         output / "readonly-agent-resume.json"],
        0,
    )
    evaluation_verification = cli(
        "readonly-agent-evaluation-services-stopped",
        [
            "verify-readonly-agent-eval",
            output / "readonly-agent-eval-manifest.json",
            output / "readonly-agent-evaluation",
        ],
        0,
    )
    summary = {"status": "passed", "evidence_kind": "synthetic-http-contract-fixture", "real_model_inference": False,
               "cases": cases, "model_semantic_quality": "unassessed",
               "agent_knowledge_policy": {
                   "status": "passed", "policy_id": agent_retrieval["policy_id"],
                   "sources": len(agent_retrieval["sources"]), "legacy_trusted_allowed": False,
               },
               "readonly_agent": {
                   "status": agent_trace["status"],
                   "semantic_status": agent_trace["semantic_status"],
                   "model_calls": agent_trace["usage"]["model_calls"],
                   "tool_calls": agent_trace["usage"]["tool_calls"],
                   "offline_verification": agent_verification["status"],
               },
               "readonly_agent_resume": {
                   "checkpoint_status": agent_checkpoint["status"],
                   "outcome_status": agent_resume["status"],
                   "outcome_kind": agent_resume["outcome_kind"],
                   "checkpoint_offline_verification": checkpoint_verification["status"],
                   "resume_offline_verification": resume_verification["status"],
                   "completed_retry_reused_output": True,
               },
               "readonly_agent_evaluation": {
                   "status": agent_evaluation["status"],
                   "manifest_id": agent_evaluation_manifest["manifest_id"],
                   "cases": agent_evaluation["summary"]["case_count"],
                   "offline_verification": evaluation_verification["status"],
                   "semantic_quality": "unassessed",
               }}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
