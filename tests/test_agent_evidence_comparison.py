from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.agent_evidence_comparison import (
    comparison_implementation_digest,
    freeze_agent_evidence_comparison,
    load_agent_evidence_comparison_manifest,
    run_agent_evidence_comparison,
    verify_agent_evidence_comparison,
    verify_agent_evidence_comparison_manifest,
)
from automotive_workbench.agent_runtime import AgentBudget
from automotive_workbench.can_io import BusConfig
from automotive_workbench.explanation_services import Endpoint
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIGEST = "a" * 64


class ComparisonClient:
    capabilities = ModelCapabilities(True, True, False, True, True)
    url = "fixture://comparison"
    records: list[dict] = []

    def service_version(self) -> str:
        return "fixture-comparison-1"

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": MODEL_DIGEST, "details": {}}

    def complete(self, payload: dict) -> dict:
        raise AssertionError("Comparison uses structured summaries")

    def usage(self, response: dict) -> dict:
        return {}

    def complete_tool_call(self, **kwargs):
        raise AssertionError("Comparison model must not choose tools")

    def complete_structured(
        self, *, model, messages, schema, max_output_tokens, context_window
    ) -> StructuredCompletion:
        content = canonical({"summary": "目标模型摘要，与冻结参考答案分开保存。"})
        return StructuredCompletion(
            content=content,
            input_tokens=60,
            output_tokens=16,
            raw={"model": model, "content": content},
        )


class AgentEvidenceComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        result = run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            cls.root / "project",
            BusConfig("virtual", "evidence-comparison"),
        )
        cls.report = Path(result["report_json"])
        knowledge = cls.root / "knowledge"
        knowledge.mkdir()
        shutil.copy2(
            ROOT / "examples/knowledge/p30-vector-official-policy.json",
            knowledge / "policy.json",
        )
        shutil.copy2(
            ROOT / "examples/knowledge/p30-vector-official-corpus.json",
            knowledge / "corpus.json",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def spec(self) -> dict:
        return {
            "comparison_id": "comparison-fixture-v1",
            "formation": "Reference was written before fixture target inference.",
            "reference_author": "fixture-agent-author",
            "reference_boundary": "Agent-authored reference, not human gold.",
            "cases": [
                {
                    "case_id": "project-handoff",
                    "category": "project-detail",
                    "report": "project/bundle/project-report.json",
                    "goal": "解释当前项目为何阻断，并说明证据边界。",
                    "scope": "project_detail",
                    "reference_answer": "参考答案：报告记录阻断；没有外部执行证据。",
                    "criteria": [
                        {
                            "criterion_id": "recorded-status",
                            "description": "准确复述记录状态。",
                        },
                        {
                            "criterion_id": "boundary",
                            "description": "不声称外部工具已执行。",
                        },
                    ],
                }
            ],
        }

    def freeze(self, directory: Path) -> tuple[Path, dict]:
        spec = directory / "spec.json"
        spec.write_text(
            json.dumps(self.spec(), ensure_ascii=False), encoding="utf-8"
        )
        manifest_path = directory / "manifest.json"
        manifest = freeze_agent_evidence_comparison(
            self.root,
            ROOT,
            spec,
            manifest_path,
            model="fixture:1",
            model_digest=MODEL_DIGEST,
            budget=AgentBudget(
                max_steps=2,
                max_model_calls=1,
                max_tool_calls=1,
                max_total_tokens=512,
                max_output_tokens_per_call=64,
                context_window=2048,
                max_seconds=30,
                max_observation_chars=20_000,
            ),
            knowledge_policy_path="knowledge/policy.json",
            knowledge_corpus_path="knowledge/corpus.json",
        )
        return manifest_path, manifest

    def test_freezes_reference_before_target_and_replays_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "result"
            result = run_agent_evidence_comparison(
                self.root,
                ROOT,
                manifest_path,
                manifest["manifest_id"],
                output,
                client=ComparisonClient(),
                knowledge_endpoint=Endpoint("http://127.0.0.1:9", 0.1),
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["semantic_status"], "pending_comparative_review")
            row = result["cases"][0]
            self.assertNotEqual(row["target_answer"], row["reference_answer"])
            self.assertEqual(row["semantic_comparison"], "pending")
            self.assertTrue(all(row["checks"].values()))
            replay = verify_agent_evidence_comparison(manifest_path, output)
            self.assertEqual(replay["comparison_status"], "passed")
            result_schema = json.loads(
                (
                    ROOT
                    / "schemas/agent-evidence-comparison-result.schema.json"
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator(result_schema).validate(result)

    def test_manifest_and_reference_tampering_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest_path, manifest = self.freeze(directory)
            changed = copy.deepcopy(manifest)
            changed["cases"][0]["reference_answer"] = "changed after inference"
            with self.assertRaisesRegex(ValueError, "manifest"):
                verify_agent_evidence_comparison_manifest(changed)
            loaded = load_agent_evidence_comparison_manifest(manifest_path)
            self.assertEqual(loaded["manifest_id"], manifest["manifest_id"])

    def test_wrong_model_and_existing_output_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest_path, manifest = self.freeze(directory)
            output = directory / "existing"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "absent"):
                run_agent_evidence_comparison(
                    self.root,
                    ROOT,
                    manifest_path,
                    manifest["manifest_id"],
                    output,
                    client=ComparisonClient(),
                    knowledge_endpoint=Endpoint("http://127.0.0.1:9", 0.1),
                )

            wrong = copy.deepcopy(manifest)
            wrong["model"]["digest"] = "b" * 64
            body = {key: wrong[key] for key in wrong if key != "manifest_id"}
            from automotive_workbench.project_explanation import digest

            wrong["manifest_id"] = digest(body)
            wrong_path = directory / "wrong.json"
            wrong_path.write_text(canonical(wrong), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model"):
                run_agent_evidence_comparison(
                    self.root,
                    ROOT,
                    wrong_path,
                    wrong["manifest_id"],
                    directory / "wrong-result",
                    client=ComparisonClient(),
                    knowledge_endpoint=Endpoint("http://127.0.0.1:9", 0.1),
                )

    def test_checked_in_manifest_matches_frozen_implementation_and_schema(self) -> None:
        manifest = load_agent_evidence_comparison_manifest(
            ROOT
            / "docs/research/p30-agent-evidence-comparison-v1-manifest.json"
        )
        self.assertEqual(
            manifest["implementation_sha256"],
            comparison_implementation_digest(ROOT),
        )
        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "agent-evidence-plan.schema.json",
                "agent-evidence-comparison-manifest.schema.json",
            )
        ]
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[2], registry=registry).validate(manifest)


if __name__ == "__main__":
    unittest.main()
