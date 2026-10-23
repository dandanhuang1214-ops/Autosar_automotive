from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.agent_evidence_pair_summary import (
    MODEL_INTERFACE,
    build_agent_evidence_pair_plan,
    run_agent_evidence_pair_summary,
    verify_agent_evidence_pair_plan,
    verify_agent_evidence_pair_summary_result,
)
from automotive_workbench.agent_evidence_pair_summary_v04 import (
    EVIDENCE_BOUNDARY,
    run_agent_evidence_pair_summary_v04,
    verify_agent_evidence_pair_summary_result_v04,
)
from automotive_workbench.agent_runtime import AgentBudget
from automotive_workbench.can_io import BusConfig
from automotive_workbench.model_client import ModelCapabilities
from automotive_workbench.project_explanation import digest
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]


class PairSummaryClient:
    capabilities = ModelCapabilities(False, False, False, True, True)

    def __init__(self) -> None:
        self.service_calls = 0
        self.identity_calls = 0
        self.calls = 0
        self.payloads: list[dict] = []

    def service_version(self) -> str:
        self.service_calls += 1
        return "fixture-pair-summary-1"

    def identity(self, name: str) -> dict:
        self.identity_calls += 1
        return {"name": name, "digest": "d" * 64, "details": {}}

    def complete(self, payload: dict) -> dict:
        self.calls += 1
        self.payloads.append(copy.deepcopy(payload))
        return {
            "model": payload["model"],
            "done": True,
            "done_reason": "stop",
            "message": {
                "role": "assistant",
                "content": (
                    "COMMUNICATION、APPLICATION、TASK-BINDINGS、MODE-RULES 均为 "
                    "passed（linked_in_scope）；IMPACT 为 passed"
                    "（explicit_dependencies_assessed）。这些静态记录不证明配置写入或实车执行。"
                ),
            },
            "prompt_eval_count": 180,
            "eval_count": 48,
            "total_duration": 1_000_000,
        }

    def complete_structured(self, **kwargs):
        raise AssertionError("The pair-summary interface is plain text")

    def complete_tool_call(self, **kwargs):
        raise AssertionError("The model cannot select pair-summary tools")


class AgentEvidencePairSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        project = run_project(
            ROOT / "examples/ecuc_acceptance/integration.project.json",
            cls.root / "project",
            BusConfig("virtual", "pair-summary"),
        )
        cls.report = Path(project["report_json"])
        transmitter = run_project(
            ROOT / "examples/ecuc_acceptance/transmitter.project.json",
            cls.root / "transmitter",
            BusConfig("virtual", "pair-summary-transmitter"),
        )
        cls.transmitter_report = Path(transmitter["report_json"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def plan(self, check_ids: list[str] | None = None) -> dict:
        return build_agent_evidence_pair_plan(
            "请给出指定静态检查各自的状态和原因，并说明证据边界。",
            check_ids
            or [
                "COMMUNICATION",
                "APPLICATION",
                "TASK-BINDINGS",
                "MODE-RULES",
                "IMPACT",
            ],
        )

    def test_complete_pairs_are_selected_before_one_plain_text_call(self) -> None:
        plan = self.plan()
        client = PairSummaryClient()
        result = run_agent_evidence_pair_summary(
            self.report, plan, client, "fixture:1"
        )

        self.assertEqual(result["protocol_status"], "passed")
        self.assertEqual(result["evidence_completeness"]["status"], "complete")
        self.assertEqual(result["evidence_completeness"]["complete_pair_count"], 5)
        self.assertEqual(result["semantic_assessment"], "unassessed")
        self.assertEqual(result["model_interface"], MODEL_INTERFACE)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result["trace"]["usage"]["tool_calls"], 1)
        self.assertEqual(result["trace"]["usage"]["model_calls"], 1)
        self.assertEqual(len(result["evidence_ids"]), 1)
        self.assertNotIn("format", client.payloads[0])
        self.assertNotIn("tools", client.payloads[0])
        context = json.loads(client.payloads[0]["messages"][1]["content"])
        self.assertEqual(context["required_check_ids"], plan["check_ids"])
        self.assertEqual(len(context["evidence_pairs"]), 5)
        self.assertEqual(
            [item["check_id"] for item in context["evidence_pairs"]],
            plan["check_ids"],
        )
        self.assertTrue(
            all(set(item) == {"check_id", "check_key", "status", "reason"}
                for item in context["evidence_pairs"])
        )
        verification = verify_agent_evidence_pair_summary_result(
            self.report, plan, result
        )
        self.assertEqual(verification["evidence_completeness"], "complete")

        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "agent-evidence-pair-plan.schema.json",
                "agent-evidence-pair-summary-result.schema.json",
            )
        ]
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[1], registry=registry).validate(plan)
        Draft202012Validator(schemas[2], registry=registry).validate(result)

    def test_missing_check_refuses_before_any_model_service_contact(self) -> None:
        plan = self.plan(["COMMUNICATION", "NOT-IN-REPORT"])
        client = PairSummaryClient()
        result = run_agent_evidence_pair_summary(
            self.report, plan, client, "fixture:1"
        )

        self.assertEqual(result["protocol_status"], "refused")
        completeness = result["evidence_completeness"]
        self.assertEqual(completeness["status"], "incomplete")
        self.assertEqual(completeness["complete_pair_count"], 1)
        self.assertEqual(completeness["checks"][1]["missing_fields"], ["status", "reason"])
        self.assertEqual(completeness["checks"][1]["issue"], "requirement_missing")
        self.assertEqual(client.service_calls, 0)
        self.assertEqual(client.identity_calls, 0)
        self.assertEqual(client.calls, 0)
        self.assertEqual(result["trace"]["usage"]["model_calls"], 0)
        self.assertIsNone(result["summary"])
        self.assertEqual(result["evidence_ids"], [])
        verify_agent_evidence_pair_summary_result(self.report, plan, result)

        budget_client = PairSummaryClient()
        over_budget = run_agent_evidence_pair_summary(
            self.report,
            self.plan(),
            budget_client,
            "fixture:1",
            AgentBudget(
                max_steps=2,
                max_model_calls=1,
                max_tool_calls=1,
                max_observation_chars=1000,
            ),
        )
        self.assertEqual(over_budget["protocol_status"], "blocked")
        self.assertEqual(
            over_budget["evidence_completeness"]["status"], "unavailable"
        )
        self.assertIn("observation budget", over_budget["trace"]["reason"])
        self.assertEqual(budget_client.service_calls, 0)
        self.assertEqual(budget_client.calls, 0)
        verify_agent_evidence_pair_summary_result(self.report, self.plan(), over_budget)

    def test_plan_and_result_tampering_fail_closed(self) -> None:
        plan = self.plan(["COMMUNICATION"])
        changed_plan = copy.deepcopy(plan)
        changed_plan["check_ids"] = ["IMPACT"]
        with self.assertRaisesRegex(ValueError, "plan"):
            verify_agent_evidence_pair_plan(changed_plan)

        result = run_agent_evidence_pair_summary(
            self.report, plan, PairSummaryClient(), "fixture:1"
        )
        with self.assertRaisesRegex(ValueError, "replayed project report"):
            verify_agent_evidence_pair_summary_result(
                self.transmitter_report, plan, result
            )
        changed = copy.deepcopy(result)
        selection = changed["trace"]["events"][0]["result"]
        selection["pairs"][0]["reason_fact"]["value"] = "invented"
        selection["selection_id"] = digest(
            {name: selection[name] for name in selection if name != "selection_id"}
        )
        tool_event = changed["trace"]["events"][0]
        tool_event["result_sha256"] = digest(selection)
        tool_event["event_id"] = digest(
            {name: tool_event[name] for name in tool_event if name != "event_id"}
        )
        model_event = changed["trace"]["events"][1]
        model_event["previous_event_id"] = tool_event["event_id"]
        model_event["event_id"] = digest(
            {name: model_event[name] for name in model_event if name != "event_id"}
        )
        trace = changed["trace"]
        trace["trace_id"] = digest(
            {name: trace[name] for name in trace if name != "trace_id"}
        )
        changed["trace_id"] = trace["trace_id"]
        changed["result_id"] = digest(
            {name: changed[name] for name in changed if name != "result_id"}
        )
        with self.assertRaisesRegex(ValueError, "fact|trace|projection|observation"):
            verify_agent_evidence_pair_summary_result(self.report, plan, changed)

    def test_v04_appends_replayable_boundary_without_rewriting_model_transcript(self) -> None:
        plan = self.plan(["COMMUNICATION"])
        client = PairSummaryClient()
        result = run_agent_evidence_pair_summary_v04(
            self.report, plan, client, "fixture:1"
        )

        self.assertEqual(result["schema_version"], "agent-evidence-pair-summary-result-0.4")
        self.assertEqual(result["protocol_status"], "passed")
        self.assertEqual(result["model_summary"], result["base_result"]["summary"])
        self.assertIn(EVIDENCE_BOUNDARY, result["summary"])
        self.assertNotIn(EVIDENCE_BOUNDARY, result["base_result"]["summary"])
        self.assertEqual(
            result["base_result"]["trace"]["final"]["summary"], result["model_summary"]
        )
        self.assertEqual(client.calls, 1)
        verified = verify_agent_evidence_pair_summary_result_v04(
            self.report, plan, result
        )
        self.assertEqual(verified["evidence_boundary"], "control_plane_appended")

        schemas = [
            json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "readonly-agent-trace.schema.json",
                "agent-evidence-pair-summary-result.schema.json",
                "agent-evidence-pair-summary-result-v0.4.schema.json",
            )
        ]
        registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas
        )
        Draft202012Validator(schemas[2], registry=registry).validate(result)

        tampered = copy.deepcopy(result)
        tampered["summary"] = tampered["model_summary"]
        tampered["result_id"] = digest(
            {name: tampered[name] for name in tampered if name != "result_id"}
        )
        with self.assertRaisesRegex(ValueError, "deterministically|differs"):
            verify_agent_evidence_pair_summary_result_v04(self.report, plan, tampered)

    def test_v04_preserves_pre_model_refusal_without_publishing_summary(self) -> None:
        plan = self.plan(["NOT-IN-REPORT"])
        client = PairSummaryClient()
        result = run_agent_evidence_pair_summary_v04(
            self.report, plan, client, "fixture:1"
        )

        self.assertEqual(result["protocol_status"], "refused")
        self.assertIsNone(result["model_summary"])
        self.assertIsNone(result["summary"])
        self.assertEqual(result["evidence_ids"], [])
        self.assertEqual(client.service_calls, 0)
        self.assertEqual(client.calls, 0)
        verify_agent_evidence_pair_summary_result_v04(self.report, plan, result)


if __name__ == "__main__":
    unittest.main()
