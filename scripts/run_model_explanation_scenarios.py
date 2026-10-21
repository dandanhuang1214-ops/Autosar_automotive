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

from automotive_workbench.project_explanation import canonical

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
    agent_evidence_plan = None
    agent_evidence_result = None
    agent_evidence_summary = None
    agent_checkpoint = None
    agent_resume = None
    agent_approval_request = None
    agent_approval_decision = None
    agent_transaction_claim = None
    agent_transaction_receipt = None
    agent_action_proposal = None
    agent_action_proposal_verification = None
    agent_action_candidate = None
    agent_candidate_selection = None
    agent_candidate_approval = None
    agent_candidate_approval_verification = None
    virtual_execution_claim = None
    virtual_execution_receipt = None
    agent_evaluation = None
    agent_evaluation_manifest = None
    agent_human_review = None
    agent_human_assessment = None
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
        evidence_plan_path = output / "agent-evidence-plan.json"
        agent_evidence_plan = cli(
            "agent-evidence-plan-create",
            [
                "create-agent-evidence-plan",
                "--goal",
                "解释项目阻断原因并说明已审核资料的适用边界",
                "--scope",
                "project_and_reviewed_knowledge",
                "--output",
                evidence_plan_path,
            ],
            0,
        )
        cli(
            "agent-evidence-plan-verify",
            ["verify-agent-evidence-plan", evidence_plan_path],
            0,
        )
        server.mode, server.tags_count = "agent_planned", 0
        evidence_result_path = output / "agent-evidence-plan-result.json"
        agent_evidence_result = cli(
            "agent-evidence-plan-run",
            [
                "run-agent-evidence-plan",
                report,
                evidence_plan_path,
                "--model",
                "fixture:1",
                "--output",
                evidence_result_path,
                "--ollama-url",
                origin,
                "--knowledge-url",
                origin,
                "--knowledge-policy",
                ROOT / "examples/knowledge/agent-read-policy.json",
                "--timeout",
                "5",
            ],
            0,
        )
        if (
            agent_evidence_result["trace"]["status"] != "passed"
            or agent_evidence_result["trace"]["usage"]["model_calls"] != 1
            or agent_evidence_result["trace"]["usage"]["tool_calls"] != 2
            or len(agent_evidence_result["trace"]["final"]["evidence_ids"]) != 2
        ):
            raise ValueError("Agent evidence plan did not bind reads and citations")
        server.mode, server.tags_count = "agent_plain_summary", 0
        evidence_summary_path = output / "agent-evidence-summary-result.json"
        agent_evidence_summary = cli(
            "agent-evidence-summary-run",
            [
                "run-agent-evidence-summary",
                report,
                evidence_plan_path,
                "--model",
                "fixture:1",
                "--output",
                evidence_summary_path,
                "--ollama-url",
                origin,
                "--knowledge-url",
                origin,
                "--knowledge-policy",
                ROOT / "examples/knowledge/agent-read-policy.json",
                "--timeout",
                "5",
            ],
            0,
        )
        summary_schema = json.loads(
            (
                ROOT / "schemas/agent-evidence-summary-result.schema.json"
            ).read_text(encoding="utf-8")
        )
        summary_registry = Registry().with_resources(
            (
                schema["$id"],
                Resource.from_contents(schema),
            )
            for schema in (
                json.loads(
                    (ROOT / "schemas/readonly-agent-trace.schema.json").read_text(
                        encoding="utf-8"
                    )
                ),
                summary_schema,
            )
        )
        Draft202012Validator(
            summary_schema, registry=summary_registry
        ).validate(agent_evidence_summary)
        if (
            agent_evidence_summary["status"] != "passed"
            or agent_evidence_summary["semantic_status"] != "unassessed"
            or agent_evidence_summary["trace"]["usage"]["model_calls"] != 1
            or agent_evidence_summary["trace"]["usage"]["tool_calls"] != 2
            or len(agent_evidence_summary["evidence_ids"]) != 2
            or "format" in agent_evidence_summary["model_exchange"]["request"]
        ):
            raise ValueError("Plain-text evidence summary contract failed")
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
        approval_arguments_path = output / "agent-approval-arguments.json"
        approval_arguments_path.write_text(
            json.dumps(
                {"object": "ComSignal/WindowPosition", "value": 42},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        approval_request_path = output / "agent-approval-request.json"
        agent_approval_request = cli(
            "agent-approval-request",
            [
                "request-agent-approval",
                checkpoint_path,
                approval_arguments_path,
                "--tool-name",
                "configuration.write",
                "--permission",
                "write",
                "--reason",
                "Operator review required; no action will execute.",
                "--evidence-id",
                agent_checkpoint["events"][-1]["observation_id"],
                "--output",
                approval_request_path,
            ],
            0,
        )
        approval_decision_path = output / "agent-approval-decision.json"
        agent_approval_decision = cli(
            "agent-approval-decision",
            [
                "decide-agent-approval",
                checkpoint_path,
                approval_request_path,
                "--decision",
                "approved",
                "--actor",
                "synthetic-local-operator",
                "--reason",
                "Recorded approval only; execution remains disabled.",
                "--output",
                approval_decision_path,
            ],
            0,
        )
        if (
            agent_approval_request["status"] != "pending"
            or agent_approval_request["execution_authorized"] is not False
            or agent_approval_decision["status"] != "approved"
            or agent_approval_decision["execution_authorized"] is not False
        ):
            raise ValueError("Agent approval record incorrectly authorized execution")
        transaction_ledger = output / "agent-transaction-ledger"
        agent_transaction_claim = cli(
            "agent-transaction-claim",
            [
                "claim-agent-approval",
                checkpoint_path,
                approval_request_path,
                approval_decision_path,
                "--ledger",
                transaction_ledger,
            ],
            0,
        )
        agent_transaction_receipt = cli(
            "agent-transaction-receipt",
            [
                "complete-agent-transaction",
                checkpoint_path,
                approval_request_path,
                approval_decision_path,
                "--ledger",
                transaction_ledger,
                "--outcome",
                "simulated",
                "--reason",
                "No side-effect tool is registered or invoked.",
            ],
            0,
        )
        if (
            agent_transaction_claim["execution_authorized"] is not False
            or agent_transaction_claim["side_effect_performed"] is not False
            or agent_transaction_receipt["status"] != "simulated"
            or agent_transaction_receipt["execution_authorized"] is not False
            or agent_transaction_receipt["side_effect_performed"] is not False
        ):
            raise ValueError("Agent transaction rehearsal performed a side effect")
        server.mode, server.tags_count = "agent_proposal", 0
        proposal_path = output / "agent-action-proposal.json"
        agent_action_proposal = cli(
            "agent-action-proposal",
            [
                "propose-agent-action", checkpoint_path,
                "--output", proposal_path,
                "--ollama-url", origin,
                "--timeout", "5",
            ],
            0,
        )
        proposal_schema = json.loads(
            (ROOT / "schemas/agent-action-proposal.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(proposal_schema).validate(agent_action_proposal)
        if (
            agent_action_proposal["status"] != "approval_required"
            or agent_action_proposal["requested_action"]["tool_name"]
            != "virtual_can.send_once"
            or agent_action_proposal["execution_authorized"] is not False
            or agent_action_proposal["tool_invoked"] is not False
        ):
            raise ValueError("Model action proposal crossed the execution boundary")
        candidate_arguments_path = output / "agent-candidate-arguments.json"
        candidate_arguments_path.write_text(
            json.dumps(
                {"frame_id": 0x456, "payload_hex": "BEEF"},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        candidate_path = output / "agent-action-candidate.json"
        agent_action_candidate = cli(
            "agent-action-candidate",
            [
                "issue-agent-action-candidate",
                checkpoint_path,
                candidate_arguments_path,
                "--tool-name",
                "virtual_can.send_once",
                "--evidence-id",
                agent_checkpoint["events"][-1]["observation_id"],
                "--output",
                candidate_path,
            ],
            0,
        )
        candidate_schema = json.loads(
            (ROOT / "schemas/agent-action-candidate.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(candidate_schema).validate(agent_action_candidate)
        server.mode, server.tags_count = "agent_candidate", 0
        candidate_selection_path = output / "agent-candidate-selection.json"
        agent_candidate_selection = cli(
            "agent-candidate-selection",
            [
                "select-agent-action-candidate",
                checkpoint_path,
                "--candidate",
                candidate_path,
                "--output",
                candidate_selection_path,
                "--ollama-url",
                origin,
                "--timeout",
                "5",
            ],
            0,
        )
        selection_schema = json.loads(
            (
                ROOT
                / "schemas/agent-action-candidate-selection.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(selection_schema).validate(
            agent_candidate_selection
        )
        if (
            agent_candidate_selection["status"] != "approval_required"
            or agent_candidate_selection["requested_action"]
            != agent_action_candidate["action"]
            or agent_candidate_selection["execution_authorized"] is not False
            or agent_candidate_selection["tool_invoked"] is not False
        ):
            raise ValueError("Candidate-ID selection changed the sealed action")
        intent_spec_path = output / "agent-action-intent-spec.json"
        intent_path = output / "agent-action-intent.json"
        admission_path = output / "agent-action-admission.json"
        evidence_value = agent_checkpoint["events"][-1]["result"]["verification"][
            "project_status"
        ]
        intent_spec_path.write_text(
            canonical(
                {
                    "disposition": "exact_action",
                    "requested_capability": {
                        "scope": "process_local_virtual",
                        "interface": "virtual",
                        "channel": None,
                    },
                    "requested_action": {
                        "tool_name": "virtual_can.send_once",
                        "arguments": {"frame_id": 0x456, "payload_hex": "BEEF"},
                    },
                    "evidence_conditions": [
                        {
                            "observation_id": agent_checkpoint["events"][-1][
                                "observation_id"
                            ],
                            "selector": {
                                "kind": "pointer",
                                "value": "/verification/project_status",
                            },
                            "expected_value": evidence_value,
                        }
                    ],
                    "deterministic_decline_reason": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        agent_action_intent = cli(
            "agent-action-intent",
            [
                "issue-agent-action-intent",
                checkpoint_path,
                intent_spec_path,
                "--output",
                intent_path,
            ],
            0,
        )
        intent_schema = json.loads(
            (ROOT / "schemas/agent-action-intent.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(intent_schema).validate(agent_action_intent)
        agent_action_admission = cli(
            "agent-action-admission",
            [
                "admit-agent-action-candidates",
                checkpoint_path,
                intent_path,
                "--candidate",
                candidate_path,
                "--output",
                admission_path,
            ],
            0,
        )
        admission_schema = json.loads(
            (ROOT / "schemas/agent-action-admission.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(admission_schema).validate(agent_action_admission)
        if (
            agent_action_admission["status"] != "approval_required"
            or agent_action_admission["requested_action"]
            != agent_action_candidate["action"]
            or agent_action_admission["model_invoked"] is not False
        ):
            raise ValueError("Deterministic admission changed the exact action")
        admission_approval_path = output / "agent-admission-approval.json"
        agent_admission_approval = cli(
            "agent-admission-approval",
            [
                "request-agent-approval-from-admission",
                checkpoint_path,
                intent_path,
                admission_path,
                "--candidate",
                candidate_path,
                "--reason",
                "Review the deterministically admitted virtual CAN frame.",
                "--output",
                admission_approval_path,
            ],
            0,
        )
        if agent_admission_approval["requested_action"] != agent_action_candidate[
            "action"
        ]:
            raise ValueError("Admission approval changed the exact action")
        cli(
            "agent-admission-approval-verification",
            [
                "verify-agent-approval-from-admission",
                checkpoint_path,
                intent_path,
                admission_path,
                admission_approval_path,
                "--candidate",
                candidate_path,
            ],
            0,
        )
        candidate_approval_path = output / "agent-candidate-approval.json"
        agent_candidate_approval = cli(
            "agent-candidate-approval",
            [
                "request-agent-approval-from-candidate",
                checkpoint_path,
                candidate_selection_path,
                "--candidate",
                candidate_path,
                "--reason",
                "Review the exact control-plane-issued virtual CAN frame.",
                "--output",
                candidate_approval_path,
            ],
            0,
        )
        if (
            agent_candidate_approval["requested_action"]
            != agent_action_candidate["action"]
        ):
            raise ValueError("Candidate approval changed the sealed action")
        agent_candidate_approval_verification = cli(
            "agent-candidate-approval-verification",
            [
                "verify-agent-approval-from-candidate",
                checkpoint_path,
                candidate_selection_path,
                candidate_approval_path,
                "--candidate",
                candidate_path,
            ],
            0,
        )
        virtual_request_path = output / "agent-virtual-can-request.json"
        virtual_request = cli(
            "agent-virtual-can-request-from-proposal",
            [
                "request-agent-approval-from-proposal", checkpoint_path,
                proposal_path,
                "--reason", "Review one isolated process-local virtual CAN frame.",
                "--output", virtual_request_path,
            ],
            0,
        )
        if (
            virtual_request["requested_action"]
            != agent_action_proposal["requested_action"]
        ):
            raise ValueError("Approval request changed the model-proposed action")
        virtual_decision_path = output / "agent-virtual-can-decision.json"
        cli(
            "agent-virtual-can-decision",
            [
                "decide-agent-approval", checkpoint_path, virtual_request_path,
                "--decision", "approved", "--actor", "synthetic-local-operator",
                "--reason", "Reviewed only; explicit local enable remains required.",
                "--output", virtual_decision_path,
            ],
            0,
        )
        virtual_ledger = output / "agent-virtual-can-ledger"
        virtual_execution_claim = cli(
            "agent-virtual-can-claim",
            [
                "claim-agent-approval", checkpoint_path, virtual_request_path,
                virtual_decision_path, "--ledger", virtual_ledger,
            ],
            0,
        )
        disabled = cli(
            "agent-virtual-can-default-disabled",
            [
                "execute-agent-virtual-can", checkpoint_path, virtual_request_path,
                virtual_decision_path, "--ledger", virtual_ledger,
            ],
            1,
        )
        if disabled.get("status") != "error" or "explicit enable" not in disabled.get("message", ""):
            raise ValueError("Agent virtual CAN execution was not disabled by default")
        if cli_python is None:
            virtual_execution_receipt = cli(
                "agent-virtual-can-execute",
                [
                    "execute-agent-virtual-can", checkpoint_path, virtual_request_path,
                    virtual_decision_path, "--ledger", virtual_ledger,
                    "--enable-virtual-execution",
                ],
                0,
            )
            if (
                virtual_execution_receipt["status"] != "succeeded"
                or virtual_execution_receipt["effect_verification"]["status"] != "passed"
                or virtual_execution_receipt["compensation"]["status"] != "passed"
                or virtual_execution_receipt["hardware_accessed"] is not False
                or virtual_execution_receipt["configuration_written"] is not False
            ):
                raise ValueError("Agent virtual CAN execution boundary failed")
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
    evidence_result_verification = cli(
        "agent-evidence-plan-result-services-stopped",
        [
            "verify-agent-evidence-plan-result",
            output / "agent-evidence-plan.json",
            output / "agent-evidence-plan-result.json",
        ],
        0,
    )
    evidence_summary_verification = cli(
        "agent-evidence-summary-services-stopped",
        [
            "verify-agent-evidence-summary-result",
            output / "agent-evidence-plan.json",
            output / "agent-evidence-summary-result.json",
        ],
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
    agent_action_proposal_verification = cli(
        "agent-action-proposal-services-stopped",
        [
            "verify-agent-action-proposal",
            output / "readonly-agent-checkpoint.json",
            output / "agent-action-proposal.json",
        ],
        0,
    )
    agent_action_candidate_verification = cli(
        "agent-action-candidate-services-stopped",
        [
            "verify-agent-action-candidate",
            output / "readonly-agent-checkpoint.json",
            output / "agent-action-candidate.json",
        ],
        0,
    )
    agent_candidate_selection_verification = cli(
        "agent-candidate-selection-services-stopped",
        [
            "verify-agent-candidate-selection",
            output / "readonly-agent-checkpoint.json",
            output / "agent-candidate-selection.json",
            "--candidate",
            output / "agent-action-candidate.json",
        ],
        0,
    )
    agent_candidate_approval_verification = cli(
        "agent-candidate-approval-services-stopped",
        [
            "verify-agent-approval-from-candidate",
            output / "readonly-agent-checkpoint.json",
            output / "agent-candidate-selection.json",
            output / "agent-candidate-approval.json",
            "--candidate",
            output / "agent-action-candidate.json",
        ],
        0,
    )
    agent_action_intent_verification = cli(
        "agent-action-intent-services-stopped",
        [
            "verify-agent-action-intent",
            output / "readonly-agent-checkpoint.json",
            output / "agent-action-intent.json",
        ],
        0,
    )
    agent_action_admission_verification = cli(
        "agent-action-admission-services-stopped",
        [
            "verify-agent-action-admission",
            output / "readonly-agent-checkpoint.json",
            output / "agent-action-intent.json",
            output / "agent-action-admission.json",
            "--candidate",
            output / "agent-action-candidate.json",
        ],
        0,
    )
    agent_admission_approval_verification = cli(
        "agent-admission-approval-services-stopped",
        [
            "verify-agent-approval-from-admission",
            output / "readonly-agent-checkpoint.json",
            output / "agent-action-intent.json",
            output / "agent-action-admission.json",
            output / "agent-admission-approval.json",
            "--candidate",
            output / "agent-action-candidate.json",
        ],
        0,
    )
    approval_request_verification = cli(
        "agent-approval-request-services-stopped",
        [
            "verify-agent-approval-request",
            output / "readonly-agent-checkpoint.json",
            output / "agent-approval-request.json",
        ],
        0,
    )
    approval_decision_verification = cli(
        "agent-approval-decision-services-stopped",
        [
            "verify-agent-approval-decision",
            output / "readonly-agent-checkpoint.json",
            output / "agent-approval-request.json",
            output / "agent-approval-decision.json",
        ],
        0,
    )
    transaction_verification = cli(
        "agent-transaction-services-stopped",
        [
            "verify-agent-transaction",
            output / "readonly-agent-checkpoint.json",
            output / "agent-approval-request.json",
            output / "agent-approval-decision.json",
            "--ledger",
            output / "agent-transaction-ledger",
        ],
        0,
    )
    virtual_execution_verification = None
    if virtual_execution_receipt is not None:
        virtual_execution_verification = cli(
            "agent-virtual-can-services-stopped",
            [
                "verify-agent-virtual-execution",
                output / "readonly-agent-checkpoint.json",
                output / "agent-virtual-can-request.json",
                output / "agent-virtual-can-decision.json",
                "--ledger", output / "agent-virtual-can-ledger",
            ],
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
    review_directory = output / "agent-human-review"
    agent_human_review = cli(
        "prepare-agent-human-review-services-stopped",
        [
            "prepare-agent-human-review",
            output / "readonly-agent-eval-manifest.json",
            output / "readonly-agent-evaluation",
            "--implementation-root",
            ROOT,
            "--output",
            review_directory,
        ],
        0,
    )
    review_verification = cli(
        "verify-agent-human-review-services-stopped",
        [
            "verify-agent-human-review",
            output / "readonly-agent-eval-manifest.json",
            output / "readonly-agent-evaluation",
            review_directory,
            "--implementation-root",
            ROOT,
        ],
        0,
    )
    completed_review = json.loads(
        (review_directory / "review-template.json").read_text(encoding="utf-8")
    )
    completed_review.update(
        {
            "status": "completed",
            "reviewer": "synthetic-contract-fixture",
            "reviewed_at": "2026-10-18T00:00:00Z",
        }
    )
    for item in completed_review["items"]:
        item.update(
            {
                "independent_expected_answer": (
                    "Synthetic protocol expectation; not a human quality judgment."
                ),
                "answer_coverage": "not_assessable",
                "causal_support": "not_assessable",
                "boundary_fidelity": "not_assessable",
                "knowledge_applicability": "not_assessable",
                "recommendation_boundary": "not_assessable",
                "usability": "not_assessable",
                "required_edits": "",
                "notes": "Exercises the immutable assessment protocol only.",
            }
        )
    completed_review_path = output / "agent-human-review-completed.json"
    completed_review_path.write_text(
        json.dumps(completed_review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assessment_path = output / "agent-human-review-assessment.json"
    agent_human_assessment = cli(
        "finalize-agent-human-review-services-stopped",
        [
            "finalize-agent-human-review",
            review_directory / "review-pack.json",
            completed_review_path,
            "--output",
            assessment_path,
        ],
        0,
    )
    assessment_verification = cli(
        "verify-agent-human-review-assessment-services-stopped",
        [
            "verify-agent-human-review-assessment",
            review_directory / "review-pack.json",
            assessment_path,
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
               "agent_evidence_plan": {
                   "plan_id": agent_evidence_plan["plan_id"],
                   "result_id": agent_evidence_result["result_id"],
                   "agent_status": agent_evidence_result["trace"]["status"],
                   "planned_tool_calls": agent_evidence_result["trace"]["usage"]["tool_calls"],
                   "model_calls": agent_evidence_result["trace"]["usage"]["model_calls"],
                   "cited_observations": len(agent_evidence_result["trace"]["final"]["evidence_ids"]),
                   "offline_verification": evidence_result_verification["status"],
                   "model_selected_tools": False,
               },
               "agent_evidence_summary": {
                   "result_id": agent_evidence_summary["result_id"],
                   "agent_status": agent_evidence_summary["status"],
                   "model_interface": agent_evidence_summary["model_interface"],
                   "planned_tool_calls": agent_evidence_summary["trace"]["usage"]["tool_calls"],
                   "model_calls": agent_evidence_summary["trace"]["usage"]["model_calls"],
                   "cited_observations": len(agent_evidence_summary["evidence_ids"]),
                   "offline_verification": evidence_summary_verification["status"],
                   "semantic_status": agent_evidence_summary["semantic_status"],
                   "model_selected_tools": False,
               },
               "readonly_agent_resume": {
                   "checkpoint_status": agent_checkpoint["status"],
                   "outcome_status": agent_resume["status"],
                   "outcome_kind": agent_resume["outcome_kind"],
                   "checkpoint_offline_verification": checkpoint_verification["status"],
                   "resume_offline_verification": resume_verification["status"],
                   "completed_retry_reused_output": True,
               },
               "readonly_agent_approval": {
                   "request_status": agent_approval_request["status"],
                   "decision_status": agent_approval_decision["status"],
                   "request_offline_verification": approval_request_verification["status"],
                   "decision_offline_verification": approval_decision_verification["status"],
                   "execution_authorized": False,
               },
               "readonly_agent_transaction": {
                   "claim_status": agent_transaction_claim["status"],
                   "receipt_status": agent_transaction_receipt["status"],
                   "offline_verification": transaction_verification["status"],
                   "execution_authorized": False,
                   "side_effect_performed": False,
               },
               "agent_action_proposal": {
                   "status": agent_action_proposal["status"],
                   "model_interface": agent_action_proposal["model_interface"],
                   "offline_verification": agent_action_proposal_verification["status"],
                   "approval_action_matches": True,
                   "execution_authorized": False,
                   "tool_invoked": False,
               },
               "agent_action_candidate": {
                   "candidate_status": agent_action_candidate_verification["status"],
                   "selection_status": agent_candidate_selection["status"],
                   "selection_offline_verification": (
                       agent_candidate_selection_verification["status"]
                   ),
                   "approval_action_matches": (
                       agent_candidate_approval["requested_action"]
                       == agent_action_candidate["action"]
                   ),
                   "approval_offline_verification": (
                       agent_candidate_approval_verification["status"]
                   ),
                   "model_supplied_action_arguments": False,
                   "execution_authorized": False,
                   "tool_invoked": False,
               },
               "agent_action_admission": {
                   "intent_status": agent_action_intent_verification["status"],
                   "admission_status": agent_action_admission["status"],
                   "admission_offline_verification": (
                       agent_action_admission_verification["status"]
                   ),
                   "approval_action_matches": (
                       agent_admission_approval["requested_action"]
                       == agent_action_candidate["action"]
                   ),
                   "approval_offline_verification": (
                       agent_admission_approval_verification["status"]
                   ),
                   "model_invoked": False,
                   "execution_authorized": False,
                   "tool_invoked": False,
               },
               "restricted_virtual_execution": {
                   "claim_status": virtual_execution_claim["status"],
                   "default_disabled": True,
                   "execution_status": (
                       "not_run_in_dependency_free_install"
                       if virtual_execution_receipt is None
                       else virtual_execution_receipt["status"]
                   ),
                   "effect_status": (
                       "not_run"
                       if virtual_execution_receipt is None
                       else virtual_execution_receipt["effect_verification"]["status"]
                   ),
                   "compensation_status": (
                       "not_run"
                       if virtual_execution_receipt is None
                       else virtual_execution_receipt["compensation"]["status"]
                   ),
                   "offline_verification": (
                       "not_run"
                       if virtual_execution_verification is None
                       else virtual_execution_verification["status"]
                   ),
                   "hardware_accessed": False,
                   "configuration_written": False,
               },
               "readonly_agent_evaluation": {
                   "status": agent_evaluation["status"],
                   "manifest_id": agent_evaluation_manifest["manifest_id"],
                   "cases": agent_evaluation["summary"]["case_count"],
                   "offline_verification": evaluation_verification["status"],
                   "semantic_quality": "unassessed",
               },
               "agent_human_review": {
                   "review_pack_id": agent_human_review["review_pack_id"],
                   "pack_offline_verification": review_verification["status"],
                   "assessment_id": agent_human_assessment["assessment_id"],
                   "assessment_offline_verification": (
                       assessment_verification["status"]
                   ),
                   "review_kind": "synthetic_protocol_not_human_judgment",
                   "semantic_quality": "unassessed",
               }}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
