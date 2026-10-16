from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from automotive_workbench.agent_candidate_evaluation import (
    candidate_evaluation_implementation_digest,
    freeze_agent_candidate_evaluation,
    load_agent_candidate_evaluation_manifest,
    run_agent_candidate_evaluation,
    verify_agent_candidate_evaluation,
)
from automotive_workbench.agent_runtime import AgentBudget, build_readonly_registry
from automotive_workbench.can_io import BusConfig
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical, digest
from automotive_workbench.project_workflow import run_project


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIGEST = "b" * 64


class CandidateEvaluationClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://candidate-evaluation"
    records: list[dict] = []

    def __init__(self, read_action: dict, *, decline: str | None = None) -> None:
        self.read_action = copy.deepcopy(read_action)
        self.decline = decline
        self.calls = 0

    def service_version(self) -> str:
        return "fixture-candidate-evaluation-1"

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": MODEL_DIGEST, "details": {}}

    def complete(self, payload: dict) -> dict:
        raise AssertionError("Evaluation must use structured completion")

    def usage(self, response: dict) -> dict:
        return {}

    def complete_structured(self, **kwargs) -> StructuredCompletion:
        self.calls += 1
        schema = kwargs["schema"]
        actions = schema["properties"]["action"].get("enum", [])
        if "select" not in actions:
            action = copy.deepcopy(self.read_action)
        elif self.decline is not None:
            action = {"action": "decline", "candidate_id": "", "reason": self.decline}
        else:
            context = json.loads(kwargs["messages"][-1]["content"])
            selected = next(
                item
                for item in context["sealed_candidates"]
                if item["action"]["arguments"]
                == {"frame_id": 0x456, "payload_hex": "BEEF"}
            )
            action = {
                "action": "select",
                "candidate_id": selected["candidate_id"],
                "reason": "",
            }
        return StructuredCompletion(
            content=canonical(action),
            input_tokens=20,
            output_tokens=5,
            raw={"call": self.calls},
        )


class AgentCandidateEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.evidence_root = Path(cls.temporary.name)
        result = run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            cls.evidence_root / "project",
            BusConfig("virtual", "agent-candidate-evaluation"),
        )
        cls.report = Path(result["report_json"])
        cls.goal = (
            "先查询诊断读取检查的状态和原因；若状态为 blocked，从控制面候选中"
            "选择标准帧 0x456、载荷 BEEF；不要执行。"
        )
        cls.budget = AgentBudget(
            max_steps=3,
            max_model_calls=3,
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
            "evaluation_id": "agent-candidate-eval-fixture",
            "split": "held-out",
            "formation": "Fixture gold and candidates were fixed before fixture inference.",
            "cases": [
                {
                    "case_id": "select-exact-sealed-frame",
                    "category": "exact-candidate-selection",
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
                    "expected": {
                        "selection_status": "approval_required",
                        "selection_reason": "model_selected_control_plane_candidate",
                        "selected_candidate_key": "wanted",
                        "first_read_tool": "project_query_facts",
                        "gold_facts": [fact],
                        "max_cumulative_model_calls": 2,
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
        manifest = freeze_agent_candidate_evaluation(
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

    def test_frozen_candidate_evaluation_runs_and_reverifies_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            result = run_agent_candidate_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=CandidateEvaluationClient(self.read_action()),
            )
            verified = verify_agent_candidate_evaluation(manifest_path, output)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["summary"]["passed_cases"], 1)
            self.assertEqual(
                result["cases"][0]["selected_candidate_key"], "wanted"
            )
            self.assertTrue(
                result["cases"][0]["checks"]["non_execution_boundary"]
            )
            self.assertEqual(verified["evaluation_status"], "passed")
            self.assertEqual(
                load_agent_candidate_evaluation_manifest(manifest_path), manifest
            )
            Draft202012Validator(
                json.loads(
                    (
                        ROOT
                        / "schemas/agent-candidate-evaluation-manifest.schema.json"
                    ).read_text(encoding="utf-8")
                )
            ).validate(manifest)
            Draft202012Validator(
                json.loads(
                    (
                        ROOT
                        / "schemas/agent-candidate-evaluation-result.schema.json"
                    ).read_text(encoding="utf-8")
                )
            ).validate(result)

    def test_checked_in_manifest_is_pre_inference_frozen_to_current_code(self) -> None:
        path = (
            ROOT
            / "docs/research/p30-agent-candidate-evaluation-v1-manifest.json"
        )
        manifest = load_agent_candidate_evaluation_manifest(path)
        self.assertEqual(
            manifest["manifest_id"],
            "718ca9f09f996b7bef0e05b2b457f860a35cbc8e6c971ef889fe07447bd5d137",
        )
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(
            manifest["implementation_sha256"],
            candidate_evaluation_implementation_digest(ROOT),
        )
        Draft202012Validator(
            json.loads(
                (
                    ROOT / "schemas/agent-candidate-evaluation-manifest.schema.json"
                ).read_text(encoding="utf-8")
            )
        ).validate(manifest)

    def test_preparation_failure_is_not_labeled_as_selection_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            decline = {
                "action": "decline",
                "tool_name": "",
                "arguments": {},
                "summary": "outside_registered_tools",
                "evidence_ids": [],
            }
            result = run_agent_candidate_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=CandidateEvaluationClient(decline),
            )
            row = result["cases"][0]
            self.assertEqual(row["preparation_kind"], "trace")
            self.assertFalse(row["checks"]["checkpoint_preparation"])
            self.assertFalse(row["checks"]["candidate_issuance"])
            self.assertIsNone(row["selection_status"])
            self.assertEqual(row["candidate_artifacts"], [])
            self.assertEqual(
                verify_agent_candidate_evaluation(manifest_path, output)[
                    "evaluation_status"
                ],
                "failed",
            )

    def test_frozen_candidate_and_result_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            spec = self.specification()
            spec["cases"][0]["candidates"][0]["arguments"]["channel"] = "can0"
            spec_path = directory / "bad-spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid virtual CAN"):
                freeze_agent_candidate_evaluation(
                    self.evidence_root,
                    ROOT,
                    spec_path,
                    directory / "bad-manifest.json",
                    model="fixture:1",
                    model_digest=MODEL_DIGEST,
                    budget=self.budget,
                )

            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            run_agent_candidate_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=CandidateEvaluationClient(self.read_action()),
            )
            result_path = output / "evaluation.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["cases"][0]["selected_candidate_key"] = "decoy"
            result["result_id"] = digest(
                {key: result[key] for key in result if key != "result_id"}
            )
            result_path.write_text(canonical(result) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact scoring"):
                verify_agent_candidate_evaluation(manifest_path, output)
