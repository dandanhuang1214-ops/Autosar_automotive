from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_evaluation import (
    freeze_agent_evaluation,
    run_agent_evaluation,
)
from automotive_workbench.agent_human_review import (
    finalize_agent_human_review,
    prepare_agent_human_review,
    verify_agent_human_review,
    verify_agent_human_review_assessment,
)
from automotive_workbench.agent_runtime import AgentBudget, build_readonly_registry
from automotive_workbench.can_io import BusConfig
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical, digest
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIGEST = "b" * 64


class ReviewClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://agent-human-review"

    def __init__(self, actions: list[dict]) -> None:
        self.actions = copy.deepcopy(actions)

    def service_version(self) -> str:
        return "fixture-human-review-1"

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": MODEL_DIGEST, "details": {}}

    def complete(self, payload: dict) -> dict:
        raise AssertionError("Human-review fixture requires structured completion")

    def usage(self, response: dict) -> dict:
        return {}

    def complete_structured(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema: dict,
        max_output_tokens: int,
        context_window: int,
    ) -> StructuredCompletion:
        action = self.actions.pop(0)
        if action["action"] == "tool":
            action.setdefault("summary", "")
            action.setdefault("evidence_ids", [])
        else:
            action.setdefault("tool_name", "")
            action.setdefault("arguments", {})
        return StructuredCompletion(
            content=canonical(action),
            input_tokens=20,
            output_tokens=5,
            raw={"model": model, "action": action},
        )


class AgentHumanReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.evidence_root = Path(cls.temporary.name)
        result = run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            cls.evidence_root / "project",
            BusConfig("virtual", "agent-human-review"),
        )
        cls.report = Path(result["report_json"])
        cls.goal = "为什么项目被阻断？请给出诊断检查状态和原因。"
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

    def _evaluation(self, directory: Path) -> tuple[Path, Path]:
        spec = {
            "evaluation_id": "agent-human-review-fixture",
            "split": "held-out",
            "formation": "Fixture formed before fixture inference.",
            "cases": [
                {
                    "case_id": "diagnostic-reason",
                    "category": "hidden-project-facts",
                    "report": "project/bundle/project-report.json",
                    "goal": self.goal,
                    "expected": {
                        "status": "passed",
                        "reason_prefix": "completed_with_unassessed_model_summary",
                        "first_tool": "project_query_facts",
                        "required_tools": ["project_query_facts"],
                        "forbidden_tools": [
                            "project_verify_report",
                            "knowledge_retrieve_reviewed",
                        ],
                        "required_evidence_tools": ["project_query_facts"],
                        "gold_facts": [
                            {
                                "artifact_id": "stage-ecuc",
                                "pointer": "/checks/diagnostic.read-version/status",
                                "value": "blocked",
                            }
                        ],
                        "knowledge_document_ids": [],
                        "max_model_calls": 2,
                        "max_tool_calls": 1,
                        "max_total_tokens": 128,
                    },
                }
            ],
        }
        spec_path = directory / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        manifest_path = directory / "manifest.json"
        manifest = freeze_agent_evaluation(
            self.evidence_root,
            ROOT,
            spec_path,
            manifest_path,
            model="fixture:review",
            model_digest=MODEL_DIGEST,
            budget=self.budget,
        )
        arguments = {"question": self.goal}
        registry = build_readonly_registry(self.report)
        result = registry.invoke("project_query_facts", arguments)
        projection = registry.project("project_query_facts", result)
        call_id = digest(
            {"tool_name": "project_query_facts", "arguments": arguments}
        )
        observation_id = digest(
            {
                "call_id": call_id,
                "result_sha256": digest(result),
                "projection_sha256": digest(projection),
            }
        )
        output = directory / "evaluation"
        run_agent_evaluation(
            self.evidence_root,
            ROOT,
            manifest_path,
            manifest["manifest_id"],
            output,
            client=ReviewClient(
                [
                    {
                        "action": "tool",
                        "tool_name": "project_query_facts",
                        "arguments": arguments,
                    },
                    {
                        "action": "finish",
                        "summary": "诊断读取检查被后端不匹配阻断。",
                        "evidence_ids": [observation_id],
                    },
                ]
            ),
        )
        return manifest_path, output

    def _completed_draft(self, template_path: Path) -> dict:
        draft = json.loads(template_path.read_text(encoding="utf-8"))
        draft.update(
            {
                "status": "completed",
                "reviewer": "independent-reviewer",
                "reviewed_at": "2026-10-18T10:30:00+08:00",
            }
        )
        for item in draft["items"]:
            item.update(
                {
                    "independent_expected_answer": "应指出检查状态及其结构化原因。",
                    "answer_coverage": "pass",
                    "causal_support": "pass",
                    "boundary_fidelity": "pass",
                    "knowledge_applicability": "not_applicable",
                    "recommendation_boundary": "pass",
                    "usability": "direct",
                    "required_edits": "",
                    "notes": "基于包内证据独立判断。",
                }
            )
        return draft

    def test_pack_is_blind_and_assessment_is_offline_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, evaluation = self._evaluation(directory)
            review = directory / "review"
            pack = prepare_agent_human_review(
                ROOT, manifest_path, evaluation, review
            )
            verification = verify_agent_human_review(
                ROOT, manifest_path, evaluation, review
            )

            serialized = canonical(pack)
            self.assertNotIn("diagnostic-reason", serialized)
            self.assertNotIn("hidden-project-facts", serialized)
            self.assertNotIn("gold_facts", serialized)
            self.assertNotIn("checks", pack["items"][0])
            self.assertEqual(pack["items"][0]["semantic_status"], "unassessed")
            self.assertEqual(len(pack["items"][0]["cited_evidence"]), 1)
            self.assertEqual(verification["semantic_status"], "pending_human_review")

            draft = self._completed_draft(review / "review-template.json")
            draft_path = directory / "completed-template.json"
            draft_path.write_text(canonical(draft) + "\n", encoding="utf-8")
            assessment_path = directory / "assessment.json"
            assessment = finalize_agent_human_review(
                review / "review-pack.json", draft_path, assessment_path
            )
            replay = verify_agent_human_review_assessment(
                review / "review-pack.json", assessment_path
            )
            self.assertEqual(assessment["summary"]["usability_counts"]["direct"], 1)
            self.assertEqual(replay["status"], "passed")

            assessment["summary"]["usability_counts"]["direct"] = 0
            assessment["assessment_id"] = digest(
                {
                    name: assessment[name]
                    for name in assessment
                    if name != "assessment_id"
                }
            )
            assessment_path.write_text(
                canonical(assessment) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "summary"):
                verify_agent_human_review_assessment(
                    review / "review-pack.json", assessment_path
                )

            for name, payload in (
                ("agent-human-review-pack", pack),
                ("agent-human-review-template", draft),
                ("agent-human-review-assessment", assessment),
            ):
                schema = json.loads(
                    (ROOT / f"schemas/{name}.schema.json").read_text(encoding="utf-8")
                )
                Draft202012Validator(
                    schema, format_checker=FormatChecker()
                ).validate(payload)

    def test_tampering_and_wrong_template_identity_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path, evaluation = self._evaluation(directory)
            review = directory / "review"
            prepare_agent_human_review(ROOT, manifest_path, evaluation, review)

            draft = self._completed_draft(review / "review-template.json")
            draft["template_id"] = "0" * 64
            draft_path = directory / "wrong-template.json"
            draft_path.write_text(canonical(draft) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "template identity"):
                finalize_agent_human_review(
                    review / "review-pack.json",
                    draft_path,
                    directory / "assessment.json",
                )

            pack_path = review / "review-pack.json"
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
            pack["items"][0]["cited_evidence"][0]["result"]["status"] = "tampered"
            pack["review_pack_id"] = digest(
                {name: pack[name] for name in pack if name != "review_pack_id"}
            )
            pack_path.write_text(canonical(pack) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "evidence"):
                verify_agent_human_review(
                    ROOT, manifest_path, evaluation, review
                )


if __name__ == "__main__":
    unittest.main()
