from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.agent_runtime import (
    AgentBudget,
    AgentRunner,
    ToolRegistry,
    ToolSpec,
    build_agent_resume_result,
    build_readonly_registry,
    resume_agent_idempotent,
    save_agent_checkpoint,
    save_agent_trace,
    verify_agent_checkpoint,
    verify_agent_resume_result,
    verify_agent_trace,
)
from automotive_workbench.can_io import BusConfig
from automotive_workbench.explanation_services import Endpoint
from automotive_workbench.knowledge_policy import policy_body
from automotive_workbench.model_client import (
    ModelCapabilities,
    OllamaModelClient,
    StructuredCompletion,
    ToolCompletion,
)
from automotive_workbench.project_explanation import canonical, digest
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://model"
    records: list[dict] = []

    def __init__(self, actions, usages=None, *, change_identity=False):
        self.actions = list(actions)
        self.usages = list(usages or [(20, 5)] * len(self.actions))
        self.change_identity = change_identity
        self.completions = 0

    def service_version(self):
        return "fixture-1"

    def identity(self, name):
        suffix = "b" if self.change_identity and self.completions else "a"
        return {"name": name, "digest": suffix * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("AgentRunner must use the structured client boundary")

    def usage(self, response):
        return {}

    def complete_structured(
        self, *, model, messages, schema, max_output_tokens, context_window
    ):
        action = copy.deepcopy(self.actions.pop(0))
        if action.get("action") == "tool":
            action.setdefault("summary", "")
            action.setdefault("evidence_ids", [])
        elif action.get("action") in {"finish", "decline"}:
            action.setdefault("tool_name", "")
            action.setdefault("arguments", {})
            action.setdefault("evidence_ids", [])
        prompt, output = self.usages.pop(0)
        self.completions += 1
        return StructuredCompletion(
            content=canonical(action),
            input_tokens=prompt,
            output_tokens=output,
            raw={"model": model, "sequence": self.completions, "action": action},
        )


class FakeNativeClient:
    capabilities = ModelCapabilities(False, True, False, True, True)
    url = "fixture://native-model"
    records: list[dict] = []

    def __init__(self, completions):
        self.completions = list(completions)
        self.tool_sets = []

    def service_version(self):
        return "fixture-native-1"

    def identity(self, name):
        return {"name": name, "digest": "c" * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("AgentRunner must use native tool calling")

    def usage(self, response):
        return {}

    def complete_structured(self, **kwargs):
        raise AssertionError("Native client must not use structured fallback")

    def complete_tool_call(
        self, *, model, messages, tools, max_output_tokens, context_window
    ):
        self.tool_sets.append(
            [item["function"]["name"] for item in copy.deepcopy(tools)]
        )
        return self.completions.pop(0)


def simple_registry(binding_context=None) -> ToolRegistry:
    registry = ToolRegistry(binding_context)
    registry.register(
        ToolSpec(
            name="project_lookup",
            description="Return one fixture fact.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["question"],
                "properties": {
                    "question": {"type": "string", "minLength": 1, "maxLength": 20}
                },
            },
            handler=lambda arguments: {
                "schema_version": "fixture-result-0.1",
                "question": arguments["question"],
                "value": "blocked",
            },
        )
    )
    return registry


def observation_id(tool_name: str, arguments: dict, result: dict) -> str:
    call_id = digest({"tool_name": tool_name, "arguments": arguments})
    return digest({
        "call_id": call_id,
        "result_sha256": digest(result),
        "projection_sha256": digest(result),
    })


class AgentRunnerTests(unittest.TestCase):
    def test_success_is_evidence_bound_and_model_summary_stays_unassessed(self):
        arguments = {"question": "status"}
        result = {
            "schema_version": "fixture-result-0.1",
            "question": "status",
            "value": "blocked",
        }
        evidence = observation_id("project_lookup", arguments, result)
        client = FakeClient(
            [
                {
                    "action": "tool",
                    "tool_name": "project_lookup",
                    "arguments": arguments,
                },
                {
                    "action": "finish",
                    "summary": "记录状态为 blocked。",
                    "evidence_ids": [evidence],
                },
            ]
        )
        trace = AgentRunner(client, simple_registry()).run("检查状态", "fixture:1")
        self.assertEqual(trace["status"], "passed")
        self.assertEqual(trace["semantic_status"], "unassessed")
        self.assertEqual(trace["final"]["semantic_status"], "unassessed")
        self.assertEqual(trace["usage"]["model_calls"], 2)
        self.assertEqual(trace["usage"]["tool_calls"], 1)
        self.assertEqual(verify_agent_trace(trace)["observation_count"], 1)
        schema = json.loads(
            (ROOT / "schemas/readonly-agent-trace.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(trace)

    def test_unknown_invalid_repeated_and_forged_calls_fail_closed(self):
        cases = [
            (
                [{"action": "tool", "tool_name": "project_unknown", "arguments": {}}],
                "Invalid Agent tool action",
            ),
            (
                [
                    {
                        "action": "tool",
                        "tool_name": "project_lookup",
                        "arguments": {"question": ""},
                    }
                ],
                "outside its bounds",
            ),
            (
                [
                    {
                        "action": "tool",
                        "tool_name": "project_lookup",
                        "arguments": {"question": "same"},
                    },
                    {
                        "action": "tool",
                        "tool_name": "project_lookup",
                        "arguments": {"question": "same"},
                    },
                ],
                "repeated_tool_call",
            ),
            (
                [
                    {
                        "action": "finish",
                        "summary": "unsupported",
                        "evidence_ids": ["0" * 64],
                    }
                ],
                "unknown_final_evidence",
            ),
        ]
        for actions, reason in cases:
            with self.subTest(reason=reason):
                trace = AgentRunner(FakeClient(actions), simple_registry()).run(
                    "goal", "fixture:1"
                )
                self.assertEqual(trace["status"], "refused")
                self.assertIn(reason, trace["reason"])
                verify_agent_trace(trace)

    def test_native_tool_loop_is_evidence_bound(self):
        arguments = {"question": "status"}
        result = {
            "schema_version": "fixture-result-0.1",
            "question": "status",
            "value": "blocked",
        }
        evidence = observation_id("project_lookup", arguments, result)
        client = FakeNativeClient(
            [
                ToolCompletion(
                    name="project_lookup",
                    arguments=arguments,
                    content="",
                    input_tokens=18,
                    output_tokens=4,
                    raw={"turn": 1},
                ),
                ToolCompletion(
                    name="agent_finish",
                    arguments={
                        "summary": "记录状态为 blocked。",
                        "evidence_ids": [evidence],
                    },
                    content="",
                    input_tokens=25,
                    output_tokens=6,
                    raw={"turn": 2},
                ),
            ]
        )
        trace = AgentRunner(client, simple_registry()).run("检查状态", "fixture:1")
        self.assertEqual(trace["status"], "passed")
        self.assertEqual(trace["usage"]["total_tokens"], 53)
        self.assertEqual(
            client.tool_sets,
            [
                ["project_lookup", "agent_finish", "agent_decline"],
                ["agent_finish", "agent_decline"],
            ],
        )
        verify_agent_trace(trace)

    def test_model_can_declare_a_bounded_policy_refusal(self):
        trace = AgentRunner(
            FakeClient(
                [
                    {
                        "action": "decline",
                        "summary": "requires_write",
                    }
                ]
            ),
            simple_registry(),
        ).run("修改配置", "fixture:1")
        self.assertEqual(trace["status"], "refused")
        self.assertEqual(trace["reason"], "model_declined:requires_write")
        self.assertEqual(trace["usage"]["tool_calls"], 0)
        self.assertIsNone(trace["final"])
        verify_agent_trace(trace)

    def test_failed_model_attempt_is_recorded_and_verifiable(self):
        client = FakeNativeClient([])

        def fail(**kwargs):
            raise ValueError("incomplete_or_invalid_tool_response")

        client.complete_tool_call = fail
        trace = AgentRunner(client, simple_registry()).run("检查状态", "fixture:1")
        self.assertEqual(trace["status"], "blocked")
        self.assertEqual(trace["usage"]["model_calls"], 1)
        self.assertEqual(len(trace["events"]), 1)
        self.assertIsNone(trace["events"][0]["response_sha256"])
        self.assertIsNone(trace["events"][0]["response_content"])
        verify_agent_trace(trace)

    def test_call_token_identity_and_time_budgets_are_hard_stops(self):
        action = {
            "action": "tool",
            "tool_name": "project_lookup",
            "arguments": {"question": "status"},
        }
        token = AgentRunner(
            FakeClient([action], usages=[(60, 10)]),
            simple_registry(),
            AgentBudget(max_steps=2, max_model_calls=2, max_tool_calls=1,
                        max_total_tokens=64),
        ).run("goal", "fixture:1")
        self.assertEqual(token["reason"], "token_budget_exhausted")
        self.assertEqual(token["usage"]["tool_calls"], 0)

        changed = AgentRunner(
            FakeClient([action], change_identity=True), simple_registry()
        ).run("goal", "fixture:1")
        self.assertEqual(changed["reason"], "model_identity_changed")
        self.assertEqual(changed["usage"]["tool_calls"], 0)

        ticks = iter([0.0, 0.6, 1.2, 1.2, 1.2])
        timed = AgentRunner(
            FakeClient([action]),
            simple_registry(),
            AgentBudget(max_steps=2, max_model_calls=2, max_tool_calls=1,
                        max_seconds=1.0),
            clock=lambda: next(ticks),
        ).run("goal", "fixture:1")
        self.assertEqual(timed["reason"], "wall_clock_budget_exhausted")
        self.assertEqual(timed["usage"]["tool_calls"], 0)

    def test_trace_tampering_and_output_overwrite_are_rejected(self):
        action = {
            "action": "tool",
            "tool_name": "project_lookup",
            "arguments": {"question": "status"},
        }
        result = {
            "schema_version": "fixture-result-0.1",
            "question": "status",
            "value": "blocked",
        }
        finish = {
            "action": "finish",
            "summary": "blocked",
            "evidence_ids": [
                observation_id("project_lookup", action["arguments"], result)
            ],
        }
        trace = AgentRunner(FakeClient([action, finish]), simple_registry()).run(
            "goal", "fixture:1"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "trace.json"
            save_agent_trace(trace, output)
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_trace(trace, output)
        changed = copy.deepcopy(trace)
        changed["events"][0]["usage"]["output_tokens"] += 1
        with self.assertRaisesRegex(ValueError, "trace ID"):
            verify_agent_trace(changed)

    def test_pause_resume_is_hash_bound_and_completed_retry_is_idempotent(self):
        arguments = {"question": "status"}
        result = {
            "schema_version": "fixture-result-0.1",
            "question": "status",
            "value": "blocked",
        }
        evidence = observation_id("project_lookup", arguments, result)
        client = FakeClient(
            [
                {
                    "action": "tool",
                    "tool_name": "project_lookup",
                    "arguments": arguments,
                },
                {
                    "action": "finish",
                    "summary": "记录状态为 blocked。",
                    "evidence_ids": [evidence],
                },
            ]
        )
        runner = AgentRunner(client, simple_registry())
        checkpoint = runner.run(
            "检查状态", "fixture:1", pause_after_tool_calls=1
        )
        self.assertEqual(checkpoint["status"], "paused")
        self.assertEqual(checkpoint["resume_count"], 0)
        self.assertEqual(checkpoint["usage"]["model_calls"], 1)
        verify_agent_checkpoint(checkpoint)

        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "readonly-agent-checkpoint.schema.json",
                "readonly-agent-resume.schema.json",
            )
        ]
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[1], registry=registry).validate(checkpoint)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint_path = root / "checkpoint.json"
            save_agent_checkpoint(checkpoint, checkpoint_path)
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_checkpoint(checkpoint, checkpoint_path)
            output = root / "resume.json"
            resumed = resume_agent_idempotent(runner, checkpoint, output)
            self.assertEqual(resumed["status"], "passed")
            self.assertEqual(resumed["outcome_kind"], "trace")
            self.assertEqual(resumed["outcome"]["usage"]["model_calls"], 2)
            self.assertEqual(
                resumed["outcome"]["events"][: len(checkpoint["events"])],
                checkpoint["events"],
            )
            verify_agent_resume_result(checkpoint, resumed)
            Draft202012Validator(schemas[2], registry=registry).validate(resumed)
            calls = client.completions
            retried = resume_agent_idempotent(runner, checkpoint, output)
            self.assertEqual(retried, resumed)
            self.assertEqual(client.completions, calls)
            with self.assertRaisesRegex(ValueError, "new parameters"):
                resume_agent_idempotent(
                    runner,
                    checkpoint,
                    output,
                    pause_after_tool_calls=1,
                )
            with self.assertRaisesRegex(ValueError, "binding differs"):
                resume_agent_idempotent(
                    AgentRunner(
                        FakeClient([]), simple_registry({"report": "different"})
                    ),
                    checkpoint,
                    output,
                )

    def test_checkpoint_and_resume_drift_fail_closed(self):
        action = {
            "action": "tool",
            "tool_name": "project_lookup",
            "arguments": {"question": "status"},
        }
        checkpoint = AgentRunner(
            FakeClient([action]), simple_registry()
        ).run("goal", "fixture:1", pause_after_tool_calls=1)
        changed = copy.deepcopy(checkpoint)
        changed["events"][-1]["model_projection"]["value"] = "passed"
        with self.assertRaisesRegex(ValueError, "checkpoint ID"):
            verify_agent_checkpoint(changed)

        different_budget = AgentRunner(
            FakeClient([]),
            simple_registry(),
            AgentBudget(max_steps=3, max_model_calls=3, max_tool_calls=2),
        )
        with self.assertRaisesRegex(ValueError, "budget differs"):
            different_budget.resume(checkpoint)

        different_binding = AgentRunner(
            FakeClient([]), simple_registry({"report_sha256": "f" * 64})
        )
        with self.assertRaisesRegex(ValueError, "binding differs"):
            different_binding.resume(checkpoint)

        changed_identity = FakeClient([], change_identity=True)
        changed_identity.completions = 1
        refused = AgentRunner(changed_identity, simple_registry()).resume(checkpoint)
        self.assertEqual(refused["status"], "refused")
        self.assertEqual(refused["reason"], "model_identity_changed")
        self.assertEqual(
            refused["usage"]["model_calls"], checkpoint["usage"]["model_calls"]
        )
        self.assertEqual(
            refused["usage"]["tool_calls"], checkpoint["usage"]["tool_calls"]
        )
        resume = build_agent_resume_result(checkpoint, refused)
        verify_agent_resume_result(checkpoint, resume)

        exhausted = AgentRunner(
            FakeClient([action]),
            simple_registry(),
            AgentBudget(max_steps=2, max_model_calls=1, max_tool_calls=1),
        ).run("goal", "fixture:1", pause_after_tool_calls=1)
        self.assertEqual(exhausted["schema_version"], "readonly-agent-trace-0.1")
        self.assertEqual(exhausted["reason"], "model_call_budget_exhausted")

    def test_resumed_pause_records_parent_checkpoint_lineage(self):
        registry = simple_registry()
        registry.register(
            ToolSpec(
                name="knowledge_lookup",
                description="Return one fixture source.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question"],
                    "properties": {
                        "question": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 20,
                        }
                    },
                },
                handler=lambda arguments: {
                    "schema_version": "fixture-source-0.1",
                    "question": arguments["question"],
                    "source": "reviewed",
                },
            )
        )
        client = FakeClient(
            [
                {
                    "action": "tool",
                    "tool_name": "project_lookup",
                    "arguments": {"question": "status"},
                },
                {
                    "action": "tool",
                    "tool_name": "knowledge_lookup",
                    "arguments": {"question": "source"},
                },
            ]
        )
        runner = AgentRunner(client, registry)
        first = runner.run("goal", "fixture:1", pause_after_tool_calls=1)
        second = runner.resume(first, pause_after_tool_calls=1)
        self.assertEqual(second["status"], "paused")
        self.assertEqual(second["resume_count"], 1)
        self.assertEqual(second["parent_checkpoint_id"], first["checkpoint_id"])
        self.assertEqual(second["events"][: len(first["events"])], first["events"])
        verify_agent_checkpoint(second)
        resume = build_agent_resume_result(
            first, second, pause_after_tool_calls=1
        )
        self.assertEqual(resume["outcome_kind"], "checkpoint")
        verify_agent_resume_result(first, resume)

    def test_registry_rejects_non_read_and_duplicate_tools(self):
        registry = ToolRegistry()
        write = ToolSpec(
            name="write.file",
            description="forbidden",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {},
            },
            handler=lambda _: {},
            permission="write",
        )
        with self.assertRaisesRegex(ValueError, "read tools"):
            registry.register(write)
        read = copy.copy(write)
        object.__setattr__(read, "permission", "read")
        registry.register(read)
        with self.assertRaisesRegex(ValueError, "unique"):
            registry.register(read)


class BoundAgentToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.report = Path(
            run_project(
                ROOT / "examples/ecuc_diagnostic/integration.project.json",
                Path(cls.temporary.name) / "project",
                BusConfig("virtual", "agent-tools"),
            )["report_json"]
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_bound_project_tools_replay_and_select_bounded_facts(self):
        registry = build_readonly_registry(self.report)
        names = [item["name"] for item in registry.manifest()]
        self.assertEqual(names, ["project_query_facts", "project_verify_report"])
        verified = registry.invoke("project_verify_report", {})
        self.assertEqual(verified["verification"]["status"], "passed")
        facts = registry.invoke(
            "project_query_facts", {"question": "为什么项目被阻断？"}
        )
        self.assertEqual(facts["project_status"], "blocked")
        self.assertLessEqual(facts["selected_fact_count"], 6)
        self.assertGreater(facts["selected_fact_count"], 0)
        projection = registry.project("project_query_facts", facts)
        self.assertNotIn("report_sha256", projection)
        self.assertNotIn("fact_id", projection["facts"][0])
        query = next(
            item for item in registry.manifest()
            if item["name"] == "project_query_facts"
        )
        self.assertEqual(query["supersedes"], ["project_verify_report"])
        available = {
            item["function"]["name"]
            for item in registry.native_tools({"project_verify_report"})
        }
        self.assertEqual(
            available,
            {"project_query_facts", "agent_finish", "agent_decline"},
        )

    def test_reviewed_knowledge_tool_is_registered_only_as_bound_pair(self):
        endpoint = Endpoint("http://localhost", 1)
        body = {
            "schema_version": "knowledge-source-policy-0.1",
            "profile": "agent-read",
            "documents": [
                {
                    "document_id": 1,
                    "document_sha256": "a" * 64,
                    "authority": "official",
                    "review": {
                        "decision": "approved",
                        "reviewer": "fixture-reviewer",
                        "reviewed_at": "2026-10-11T00:00:00Z",
                    },
                }
            ],
        }
        policy = {**body, "policy_id": digest(body)}
        self.assertEqual(policy_body(policy), body)
        with self.assertRaisesRegex(ValueError, "configured together"):
            build_readonly_registry(self.report, knowledge_endpoint=endpoint)
        registry = build_readonly_registry(
            self.report, knowledge_endpoint=endpoint, knowledge_policy=policy
        )
        item = {
            "chunk_id": 10,
            "document_id": 1,
            "content": "Reviewed text",
            "page": 1,
            "title": "Manual",
        }
        document = {
            "id": 1,
            "enabled": True,
            "status": "ready",
            "review_status": "approved",
            "authority": "official",
            "sha256": "a" * 64,
        }
        with patch.object(
            endpoint,
            "request",
            side_effect=[{"query": "timeout", "results": [item]}, [document], item],
        ):
            result = registry.invoke(
                "knowledge_retrieve_reviewed", {"question": "timeout"}
            )
        self.assertEqual(result["policy_id"], policy["policy_id"])
        self.assertEqual(result["sources"][0]["authority"], "official")

    def test_bound_report_cannot_change_after_registry_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "project-report.json"
            copied.write_bytes(self.report.read_bytes())
            registry = build_readonly_registry(copied)
            copied.write_bytes(copied.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "bound report changed"):
                registry.invoke("project_verify_report", {})


class StructuredModelClientTests(unittest.TestCase):
    def test_ollama_boundary_builds_bounded_payload_and_requires_usage(self):
        endpoint = Endpoint("http://localhost", 1)
        client = OllamaModelClient(endpoint)
        response = {
            "model": "fixture:1",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": '{"ok":true}'},
            "prompt_eval_count": 12,
            "eval_count": 3,
        }
        with patch.object(endpoint, "request", return_value=response) as request:
            result = client.complete_structured(
                model="fixture:1",
                messages=[{"role": "user", "content": "goal"}],
                schema={"type": "object"},
                max_output_tokens=64,
                context_window=1024,
            )
        self.assertEqual((result.input_tokens, result.output_tokens), (12, 3))
        payload = request.call_args.args[1]
        self.assertEqual(payload["think"], False)
        self.assertEqual(payload["options"]["num_predict"], 64)
        bad = {**response, "eval_count": True}
        with patch.object(endpoint, "request", return_value=bad):
            with self.assertRaisesRegex(ValueError, "context_budget"):
                client.complete_structured(
                    model="fixture:1",
                    messages=[{"role": "user", "content": "goal"}],
                    schema={"type": "object"},
                    max_output_tokens=64,
                    context_window=1024,
                )

        tool_response = {
            **response,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "index": 0,
                            "name": "project_verify_report",
                            "arguments": {},
                        }
                    }
                ],
            },
        }
        with patch.object(endpoint, "request", return_value=tool_response) as request:
            turn = client.complete_tool_call(
                model="fixture:1",
                messages=[{"role": "user", "content": "goal"}],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "project_verify_report",
                            "description": "verify",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
                max_output_tokens=64,
                context_window=1024,
            )
        self.assertEqual(turn.name, "project_verify_report")
        self.assertEqual(turn.arguments, {})
        self.assertIn("tools", request.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
