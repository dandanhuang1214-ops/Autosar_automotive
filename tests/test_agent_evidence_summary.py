from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.agent_evidence_plan import build_agent_evidence_plan
from automotive_workbench.agent_evidence_summary import (
    MODEL_INTERFACE,
    run_agent_evidence_summary,
    save_agent_evidence_summary_result,
    verify_agent_evidence_summary_result,
)
from automotive_workbench.agent_runtime import AgentBudget, ToolRegistry, ToolSpec
from automotive_workbench.model_client import ModelCapabilities
from automotive_workbench.project_explanation import digest

ROOT = Path(__file__).resolve().parents[1]


class PlainTextClient:
    capabilities = ModelCapabilities(False, False, False, True, True)
    url = "fixture://plain-text-summary"
    records: list[dict] = []

    def __init__(
        self,
        content: str = "项目记录为 blocked；现有证据不证明外部工具已执行。",
        *,
        done_reason: str = "stop",
        drift: bool = False,
        eval_count: int = 24,
    ) -> None:
        self.content = content
        self.done_reason = done_reason
        self.drift = drift
        self.eval_count = eval_count
        self.calls = 0
        self.identities = 0
        self.payloads: list[dict] = []

    def service_version(self):
        return "fixture-plain-text-1"

    def identity(self, name):
        self.identities += 1
        suffix = "e" if self.drift and self.identities > 1 else "d"
        return {"name": name, "digest": suffix * 64, "details": {}}

    def complete(self, payload):
        self.calls += 1
        self.payloads.append(copy.deepcopy(payload))
        return {
            "model": payload["model"],
            "done": True,
            "done_reason": self.done_reason,
            "message": {"role": "assistant", "content": self.content},
            "prompt_eval_count": 80,
            "eval_count": self.eval_count,
            "total_duration": 1_000_000,
        }

    def usage(self, response):
        return {}

    def complete_structured(self, **kwargs):
        raise AssertionError("The 0.2 interface must not request structured output")

    def complete_tool_call(self, **kwargs):
        raise AssertionError("The 0.2 interface must not expose model-selected tools")


def registry() -> ToolRegistry:
    value = ToolRegistry({"fixture": "plain-text-summary"})
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


class AgentEvidenceSummaryTests(unittest.TestCase):
    def test_plain_text_interface_keeps_plan_and_citations_in_control_plane(self) -> None:
        plan = build_agent_evidence_plan(
            "解释项目状态并说明官方资料边界。",
            "project_and_reviewed_knowledge",
        )
        client = PlainTextClient(content="  记录为 blocked；资料不证明命令已运行。\n")
        result = run_agent_evidence_summary(plan, registry(), client, "fixture:1")
        trace = result["trace"]

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["model_interface"], MODEL_INTERFACE)
        self.assertEqual(result["summary"], "记录为 blocked；资料不证明命令已运行。")
        self.assertEqual(trace["reason"], "completed_with_control_plane_plain_text_summary")
        self.assertEqual(trace["usage"]["model_calls"], 1)
        self.assertEqual(trace["usage"]["tool_calls"], 2)
        observations = [
            event["observation_id"]
            for event in trace["events"]
            if event["kind"] == "tool"
        ]
        self.assertEqual(result["evidence_ids"], observations)
        self.assertEqual(trace["final"]["evidence_ids"], observations)
        self.assertNotIn("format", client.payloads[0])
        self.assertNotIn("tools", client.payloads[0])
        self.assertIs(client.payloads[0]["think"], False)
        self.assertEqual(
            result["model_exchange"]["response"]["message"]["content"],
            "  记录为 blocked；资料不证明命令已运行。\n",
        )
        verification = verify_agent_evidence_summary_result(plan, result)
        self.assertEqual(verification["cited_observations"], 2)

        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "agent-evidence-plan.schema.json",
                "agent-evidence-summary-result.schema.json",
            )
        ]
        schema_registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[2], registry=schema_registry).validate(result)

    def test_invalid_response_and_identity_drift_publish_no_answer(self) -> None:
        plan = build_agent_evidence_plan("解释项目状态。", "project_detail")
        incomplete = run_agent_evidence_summary(
            plan,
            registry(),
            PlainTextClient(content="未完成", done_reason="length"),
            "fixture:1",
        )
        self.assertEqual(incomplete["status"], "blocked")
        self.assertIsNone(incomplete["summary"])
        self.assertEqual(incomplete["evidence_ids"], [])
        self.assertEqual(
            incomplete["trace"]["events"][-1]["response_content"], "未完成"
        )
        self.assertIn("incomplete", incomplete["trace"]["reason"])
        verify_agent_evidence_summary_result(plan, incomplete)

        oversized = run_agent_evidence_summary(
            plan, registry(), PlainTextClient(content="x" * 8001), "fixture:1"
        )
        self.assertEqual(oversized["status"], "blocked")
        self.assertIsNone(oversized["summary"])
        self.assertEqual(
            len(oversized["trace"]["events"][-1]["response_content"]), 8000
        )
        self.assertEqual(
            len(oversized["model_exchange"]["response"]["message"]["content"]),
            8001,
        )
        verify_agent_evidence_summary_result(plan, oversized)

        over_budget = run_agent_evidence_summary(
            plan, registry(), PlainTextClient(eval_count=513), "fixture:1"
        )
        self.assertEqual(over_budget["status"], "refused")
        self.assertEqual(
            over_budget["trace"]["reason"], "model_output_token_budget_exhausted"
        )
        self.assertIsNone(over_budget["summary"])
        verify_agent_evidence_summary_result(plan, over_budget)

        drifted = run_agent_evidence_summary(
            plan, registry(), PlainTextClient(drift=True), "fixture:1"
        )
        self.assertEqual(drifted["status"], "refused")
        self.assertEqual(drifted["trace"]["reason"], "model_identity_changed")
        self.assertIsNone(drifted["summary"])
        verify_agent_evidence_summary_result(plan, drifted)

    def test_tampering_budget_and_output_overwrite_fail_closed(self) -> None:
        plan = build_agent_evidence_plan("解释项目和资料。", "project_and_reviewed_knowledge")
        client = PlainTextClient()
        with self.assertRaisesRegex(ValueError, "tool-call budget"):
            run_agent_evidence_summary(
                plan,
                registry(),
                client,
                "fixture:1",
                AgentBudget(max_steps=2, max_model_calls=1, max_tool_calls=1),
            )
        self.assertEqual(client.calls, 0)

        result = run_agent_evidence_summary(plan, registry(), client, "fixture:1")
        changed = copy.deepcopy(result)
        changed["summary"] = "被篡改"
        with self.assertRaisesRegex(ValueError, "result|plan-bound"):
            verify_agent_evidence_summary_result(plan, changed)

        changed_exchange = copy.deepcopy(result)
        changed_exchange["model_exchange"]["request"]["format"] = {"type": "object"}
        changed_exchange["result_id"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "result|plain-text"):
            verify_agent_evidence_summary_result(plan, changed_exchange)

        coherently_rehashed = copy.deepcopy(result)
        request = coherently_rehashed["model_exchange"]["request"]
        request["messages"][1]["content"] = "{}"
        model_event = coherently_rehashed["trace"]["events"][-1]
        model_event["request_sha256"] = digest(request)
        model_event["event_id"] = digest(
            {name: model_event[name] for name in model_event if name != "event_id"}
        )
        trace = coherently_rehashed["trace"]
        trace["trace_id"] = digest(
            {name: trace[name] for name in trace if name != "trace_id"}
        )
        coherently_rehashed["trace_id"] = trace["trace_id"]
        coherently_rehashed["result_id"] = digest(
            {
                name: coherently_rehashed[name]
                for name in coherently_rehashed
                if name != "result_id"
            }
        )
        with self.assertRaisesRegex(ValueError, "plain-text request"):
            verify_agent_evidence_summary_result(plan, coherently_rehashed)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "summary.json"
            save_agent_evidence_summary_result(plan, result, path)
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_evidence_summary_result(plan, result, path)


if __name__ == "__main__":
    unittest.main()
