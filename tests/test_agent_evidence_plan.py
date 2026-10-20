from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.agent_evidence_plan import (
    build_agent_evidence_plan,
    run_agent_evidence_plan,
    save_agent_evidence_plan,
    save_agent_evidence_plan_result,
    verify_agent_evidence_plan,
    verify_agent_evidence_plan_result,
)
from automotive_workbench.agent_runtime import AgentBudget, ToolRegistry, ToolSpec
from automotive_workbench.model_client import (
    ModelCapabilities,
    StructuredCompletion,
)
from automotive_workbench.project_explanation import canonical

ROOT = Path(__file__).resolve().parents[1]


class SummaryClient:
    capabilities = ModelCapabilities(True, True, False, True, True)
    url = "fixture://planned-summary"
    records: list[dict] = []

    def __init__(self, summary: str = "记录事实与资料边界；未执行外部工具。") -> None:
        self.summary = summary
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    def service_version(self):
        return "fixture-planned-1"

    def identity(self, name):
        return {"name": name, "digest": "d" * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("Planned summary must use structured output")

    def usage(self, response):
        return {}

    def complete_tool_call(self, **kwargs):
        raise AssertionError("The model must not select planned read tools or finish")

    def complete_structured(
        self, *, model, messages, schema, max_output_tokens, context_window
    ):
        self.calls += 1
        self.messages.append(copy.deepcopy(messages))
        content = canonical({"summary": self.summary})
        return StructuredCompletion(
            content=content,
            input_tokens=70,
            output_tokens=20,
            raw={"model": model, "content": content, "call": self.calls},
        )


def registry() -> ToolRegistry:
    value = ToolRegistry({"fixture": "planned"})
    value.register(
        ToolSpec(
            name="project_query_facts",
            description="Return detailed project facts.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["question"],
                "properties": {
                    "question": {"type": "string", "minLength": 1, "maxLength": 2000}
                },
            },
            handler=lambda arguments: {
                "schema_version": "fixture-project-facts-0.1",
                "question": arguments["question"],
                "facts": [{"pointer": "/status", "value": "blocked"}],
            },
        )
    )
    value.register(
        ToolSpec(
            name="knowledge_retrieve_reviewed",
            description="Return reviewed official knowledge.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["question"],
                "properties": {
                    "question": {"type": "string", "minLength": 1, "maxLength": 2000}
                },
            },
            handler=lambda arguments: {
                "schema_version": "fixture-reviewed-knowledge-0.1",
                "question": arguments["question"],
                "sources": [{"document_id": 1, "excerpt": "Official scope."}],
            },
        )
    )
    return value


class AgentEvidencePlanTests(unittest.TestCase):
    def test_control_plane_runs_exact_reads_and_attaches_every_citation(self) -> None:
        plan = build_agent_evidence_plan(
            "解释项目状态并说明官方资料边界。",
            "project_and_reviewed_knowledge",
        )
        client = SummaryClient()
        result = run_agent_evidence_plan(plan, registry(), client, "fixture:1")
        trace = result["trace"]

        self.assertEqual(result["status"], "passed")
        self.assertEqual(trace["status"], "passed")
        self.assertEqual(trace["reason"], "completed_with_control_plane_evidence_plan")
        self.assertEqual(trace["usage"]["model_calls"], 1)
        self.assertEqual(trace["usage"]["tool_calls"], 2)
        self.assertEqual(
            [event["kind"] for event in trace["events"]],
            ["tool", "tool", "model"],
        )
        observations = [
            event["observation_id"]
            for event in trace["events"]
            if event["kind"] == "tool"
        ]
        self.assertEqual(trace["final"]["evidence_ids"], observations)
        self.assertNotIn("tools", json.loads(client.messages[0][1]["content"]))
        verification = verify_agent_evidence_plan_result(plan, result)
        self.assertEqual(verification["cited_observations"], 2)

        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "agent-evidence-plan.schema.json",
                "agent-evidence-plan-result.schema.json",
            )
        ]
        schema_registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[1], registry=schema_registry).validate(plan)
        Draft202012Validator(schemas[2], registry=schema_registry).validate(result)

    def test_scope_and_plan_tampering_fail_closed(self) -> None:
        plan = build_agent_evidence_plan("解释阻断原因。", "project_detail")
        changed = copy.deepcopy(plan)
        changed["steps"][0]["tool_name"] = "project_verify_report"
        with self.assertRaisesRegex(ValueError, "deterministic scope"):
            verify_agent_evidence_plan(changed)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            build_agent_evidence_plan("goal", "write_configuration")

        result = run_agent_evidence_plan(plan, registry(), SummaryClient(), "fixture:1")
        changed_result = copy.deepcopy(result)
        changed_result["trace"]["final"]["evidence_ids"] = []
        with self.assertRaisesRegex(ValueError, "result|trace|answer"):
            verify_agent_evidence_plan_result(plan, changed_result)

        changed_status = copy.deepcopy(result)
        changed_status["status"] = "blocked"
        with self.assertRaisesRegex(ValueError, "result|trace"):
            verify_agent_evidence_plan_result(plan, changed_status)

    def test_missing_bound_tool_and_budget_are_rejected_before_inference(self) -> None:
        plan = build_agent_evidence_plan("只查官方资料。", "reviewed_knowledge")
        project_only = ToolRegistry()
        project_only.register(
            ToolSpec(
                name="project_query_facts",
                description="Project only.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question"],
                    "properties": {
                        "question": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 2000,
                        }
                    },
                },
                handler=lambda arguments: arguments,
            )
        )
        client = SummaryClient()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            run_agent_evidence_plan(plan, project_only, client, "fixture:1")
        self.assertEqual(client.calls, 0)

        mixed = build_agent_evidence_plan(
            "查询项目和官方资料。", "project_and_reviewed_knowledge"
        )
        with self.assertRaisesRegex(ValueError, "tool-call budget"):
            run_agent_evidence_plan(
                mixed,
                registry(),
                client,
                "fixture:1",
                AgentBudget(max_steps=2, max_model_calls=1, max_tool_calls=1),
            )
        self.assertEqual(client.calls, 0)

    def test_saved_plan_and_result_are_no_overwrite_offline_artifacts(self) -> None:
        plan = build_agent_evidence_plan("解释项目事实。", "project_detail")
        result = run_agent_evidence_plan(plan, registry(), SummaryClient(), "fixture:1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path = root / "plan.json"
            result_path = root / "result.json"
            save_agent_evidence_plan(plan, plan_path)
            save_agent_evidence_plan_result(plan, result, result_path)
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_evidence_plan(plan, plan_path)
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_evidence_plan_result(plan, result, result_path)


if __name__ == "__main__":
    unittest.main()
