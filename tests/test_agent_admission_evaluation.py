from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from automotive_workbench.agent_admission_evaluation import (
    admission_evaluation_implementation_digest,
    freeze_agent_admission_evaluation,
    load_agent_admission_evaluation_manifest,
    run_agent_admission_evaluation,
    verify_agent_admission_evaluation,
)
from automotive_workbench.agent_runtime import AgentBudget, build_readonly_registry
from automotive_workbench.can_io import BusConfig
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical, digest
from automotive_workbench.project_workflow import run_project


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIGEST = "c" * 64


class AdmissionEvaluationClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://admission-evaluation"

    def __init__(self, read_action: dict) -> None:
        self.read_action = copy.deepcopy(read_action)
        self.calls = 0

    def service_version(self) -> str:
        return "fixture-admission-evaluation-1"

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": MODEL_DIGEST, "details": {}}

    def complete(self, payload: dict) -> dict:
        raise AssertionError("Evaluation must use structured completion")

    def usage(self, response: dict) -> dict:
        return {}

    def complete_structured(self, **kwargs) -> StructuredCompletion:
        self.calls += 1
        return StructuredCompletion(
            content=canonical(self.read_action),
            input_tokens=20,
            output_tokens=5,
            raw={"call": self.calls},
        )


class AgentAdmissionEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.evidence_root = Path(cls.temporary.name)
        result = run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            cls.evidence_root / "project",
            BusConfig("virtual", "agent-admission-evaluation"),
        )
        cls.report = Path(result["report_json"])
        cls.goal = (
            "先只查询诊断读取检查的状态和原因并暂停；控制面随后按已冻结意图"
            "确定性处理标准帧 0x456、载荷 BEEF，不要执行。"
        )
        cls.budget = AgentBudget(
            max_steps=2,
            max_model_calls=2,
            max_tool_calls=1,
            max_total_tokens=512,
            max_output_tokens_per_call=64,
            context_window=2048,
            max_seconds=30,
            max_observation_chars=20_000,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def specification(self) -> dict:
        fact = {
            "artifact_id": "stage-ecuc",
            "pointer": "/checks/diagnostic.read-version/status",
            "value": "blocked",
        }
        return {
            "evaluation_id": "agent-admission-eval-fixture",
            "split": "held-out",
            "formation": "Fixture intent and gold were fixed before fixture inference.",
            "cases": [
                {
                    "case_id": "admit-exact-sealed-frame",
                    "category": "exact-deterministic-admission",
                    "report": "project/bundle/project-report.json",
                    "goal": self.goal,
                    "candidates": [
                        {
                            "candidate_key": "decoy",
                            "tool_name": "virtual_can.send_once",
                            "arguments": {"frame_id": 1, "payload_hex": "BEEF"},
                            "evidence_gold_facts": [fact],
                        },
                        {
                            "candidate_key": "wanted",
                            "tool_name": "virtual_can.send_once",
                            "arguments": {"frame_id": 0x456, "payload_hex": "BEEF"},
                            "evidence_gold_facts": [fact],
                        },
                    ],
                    "intent": {
                        "disposition": "exact_action",
                        "requested_capability": {
                            "scope": "process_local_virtual",
                            "interface": "virtual",
                            "channel": None,
                        },
                        "requested_action_candidate_key": "wanted",
                        "evidence_conditions": [
                            {"fact": fact, "expected_value": "blocked"}
                        ],
                        "deterministic_decline_reason": None,
                    },
                    "expected": {
                        "admission_status": "approval_required",
                        "admission_reason": "control_plane_exact_candidate_admitted",
                        "selected_candidate_key": "wanted",
                        "first_read_tool": "project_query_facts",
                        "gold_facts": [fact],
                        "max_cumulative_model_calls": 1,
                        "max_cumulative_total_tokens": 128,
                    },
                }
            ],
        }

    def freeze(self, directory: Path) -> tuple[Path, dict]:
        spec_path = directory / "spec.json"
        spec_path.write_text(
            json.dumps(self.specification(), ensure_ascii=False), encoding="utf-8"
        )
        manifest_path = directory / "manifest.json"
        manifest = freeze_agent_admission_evaluation(
            self.evidence_root,
            ROOT,
            spec_path,
            manifest_path,
            model="fixture:1",
            model_digest=MODEL_DIGEST,
            budget=self.budget,
        )
        return manifest_path, manifest

    def read_action(self) -> dict:
        registry = build_readonly_registry(self.report)
        arguments = {"question": self.goal}
        self.assertTrue(registry.invoke("project_query_facts", arguments)["facts"])
        return {
            "action": "tool",
            "tool_name": "project_query_facts",
            "arguments": arguments,
            "summary": "",
            "evidence_ids": [],
        }

    def test_frozen_admission_evaluation_runs_once_and_reverifies_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            client = AdmissionEvaluationClient(self.read_action())
            result = run_agent_admission_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=client,
            )
            verified = verify_agent_admission_evaluation(manifest_path, output)

            self.assertEqual(client.calls, 1)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["summary"]["passed_cases"], 1)
            self.assertEqual(result["cases"][0]["selected_candidate_key"], "wanted")
            self.assertTrue(result["cases"][0]["checks"]["non_execution_boundary"])
            self.assertEqual(verified["evaluation_status"], "passed")
            self.assertEqual(load_agent_admission_evaluation_manifest(manifest_path), manifest)
            for name, value in (
                ("agent-admission-evaluation-manifest.schema.json", manifest),
                ("agent-admission-evaluation-result.schema.json", result),
            ):
                Draft202012Validator(
                    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
                ).validate(value)

    def test_preparation_failure_is_separate_from_deterministic_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            declined = {
                "action": "decline",
                "tool_name": "",
                "arguments": {},
                "summary": "outside_registered_tools",
                "evidence_ids": [],
            }
            result = run_agent_admission_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=AdmissionEvaluationClient(declined),
            )
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["cases"][0]["checks"]["checkpoint_preparation"])
            self.assertFalse(result["cases"][0]["checks"]["intent_issuance"])
            self.assertIsNone(result["cases"][0]["admission_status"])
            self.assertEqual(
                verify_agent_admission_evaluation(manifest_path, output)["status"],
                "passed",
            )

    def test_result_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            run_agent_admission_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=AdmissionEvaluationClient(self.read_action()),
            )
            result = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
            result["cases"][0]["admission_reason"] = "tampered"
            result["result_id"] = digest(
                {key: result[key] for key in result if key != "result_id"}
            )
            (output / "evaluation.json").write_text(canonical(result) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from artifact scoring"):
                verify_agent_admission_evaluation(manifest_path, output)

    def test_checked_in_manifest_is_pre_inference_frozen_to_current_code(self) -> None:
        path = ROOT / "docs/research/p30-agent-admission-evaluation-v1-manifest.json"
        manifest = load_agent_admission_evaluation_manifest(path)
        self.assertEqual(
            manifest["manifest_id"],
            "945dfd72145acdc97a100d1d7f54bc5afafac7326d331278a2d59f56b4b0100a",
        )
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(
            manifest["implementation_sha256"],
            admission_evaluation_implementation_digest(ROOT),
        )


if __name__ == "__main__":
    unittest.main()
