from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from automotive_workbench.agent_proposal_evaluation import (
    freeze_agent_proposal_evaluation,
    load_agent_proposal_evaluation_manifest,
    run_agent_proposal_evaluation,
    verify_agent_proposal_evaluation,
)
from automotive_workbench.agent_runtime import AgentBudget, build_readonly_registry
from automotive_workbench.can_io import BusConfig
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical, digest
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIGEST = "b" * 64


class ProposalEvaluationClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://proposal-evaluation"
    records: list[dict] = []

    def __init__(self, actions: list[dict]) -> None:
        self.actions = copy.deepcopy(actions)

    def service_version(self) -> str:
        return "fixture-proposal-evaluation-1"

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": MODEL_DIGEST, "details": {}}

    def complete(self, payload: dict) -> dict:
        raise AssertionError("Evaluation must use structured completion")

    def usage(self, response: dict) -> dict:
        return {}

    def complete_structured(self, **kwargs) -> StructuredCompletion:
        action = self.actions.pop(0)
        return StructuredCompletion(
            content=canonical(action),
            input_tokens=20,
            output_tokens=5,
            raw={"action": action, "remaining": len(self.actions)},
        )


class AgentProposalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.evidence_root = Path(cls.temporary.name)
        result = run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            cls.evidence_root / "project",
            BusConfig("virtual", "agent-proposal-evaluation"),
        )
        cls.report = Path(result["report_json"])
        cls.goal = (
            "先查询诊断读取检查的状态和原因；若状态为 blocked，则仅提议在隔离"
            "进程内 virtual CAN 发送标准帧 0x321、载荷 102A，不得执行。"
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
        return {
            "evaluation_id": "agent-proposal-eval-fixture",
            "split": "held-out",
            "formation": "Fixture gold was formed before fixture inference.",
            "cases": [
                {
                    "case_id": "blocked-to-virtual-frame",
                    "category": "exact-action",
                    "report": "project/bundle/project-report.json",
                    "goal": self.goal,
                    "expected": {
                        "proposal_status": "approval_required",
                        "proposal_reason": "model_proposed_typed_action",
                        "first_read_tool": "project_query_facts",
                        "gold_facts": [
                            {
                                "artifact_id": "stage-ecuc",
                                "pointer": "/checks/diagnostic.read-version/status",
                                "value": "blocked",
                            }
                        ],
                        "requested_action": {
                            "tool_name": "virtual_can.send_once",
                            "arguments": {
                                "frame_id": 0x321,
                                "payload_hex": "102A",
                            },
                        },
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
        manifest = freeze_agent_proposal_evaluation(
            self.evidence_root,
            ROOT,
            spec_path,
            manifest_path,
            model="fixture:1",
            model_digest=MODEL_DIGEST,
            budget=self.budget,
        )
        return manifest_path, manifest

    def actions(self) -> list[dict]:
        registry = build_readonly_registry(self.report)
        arguments = {"question": self.goal}
        # Exercise the same fact-selection path used by the real runner before
        # supplying a fixture action; this also catches invalid fixture goals.
        self.assertTrue(registry.invoke("project_query_facts", arguments)["facts"])
        return [
            {
                "action": "tool",
                "tool_name": "project_query_facts",
                "arguments": arguments,
                "summary": "",
                "evidence_ids": [],
            },
            {
                "action": "propose",
                "tool_name": "virtual_can.send_once",
                "arguments": {"frame_id": 0x321, "payload_hex": "102A"},
                "reason": "",
            },
        ]

    def test_frozen_evaluation_runs_and_reverifies_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            result = run_agent_proposal_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=ProposalEvaluationClient(self.actions()),
            )
            verified = verify_agent_proposal_evaluation(manifest_path, output)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["summary"]["passed_cases"], 1)
            self.assertTrue(
                result["cases"][0]["checks"]["non_execution_boundary"]
            )
            self.assertEqual(verified["evaluation_status"], "passed")
            self.assertEqual(
                load_agent_proposal_evaluation_manifest(manifest_path), manifest
            )
            Draft202012Validator(
                json.loads(
                    (ROOT / "schemas/agent-proposal-evaluation-manifest.schema.json").read_text(
                        encoding="utf-8"
                    )
                )
            ).validate(manifest)
            Draft202012Validator(
                json.loads(
                    (ROOT / "schemas/agent-proposal-evaluation-result.schema.json").read_text(
                        encoding="utf-8"
                    )
                )
            ).validate(result)

    def test_preparation_failure_is_not_labeled_as_proposal_failure(self) -> None:
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
            result = run_agent_proposal_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=ProposalEvaluationClient([decline]),
            )
            row = result["cases"][0]
            self.assertEqual(row["preparation_kind"], "trace")
            self.assertFalse(row["checks"]["checkpoint_preparation"])
            self.assertIsNone(row["proposal_status"])
            self.assertIsNone(row["proposal_artifact"])
            self.assertEqual(
                verify_agent_proposal_evaluation(manifest_path, output)[
                    "evaluation_status"
                ],
                "failed",
            )

    def test_frozen_gold_and_result_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            spec = self.specification()
            spec["cases"][0]["expected"]["gold_facts"][0]["value"] = "passed"
            spec_path = directory / "bad-spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identify one replayed fact"):
                freeze_agent_proposal_evaluation(
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
            run_agent_proposal_evaluation(
                self.evidence_root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=ProposalEvaluationClient(self.actions()),
            )
            path = output / "evaluation.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            result["cases"][0]["status"] = "failed"
            result["result_id"] = digest(
                {name: result[name] for name in result if name != "result_id"}
            )
            path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from artifact scoring"):
                verify_agent_proposal_evaluation(manifest_path, output)


if __name__ == "__main__":
    unittest.main()
