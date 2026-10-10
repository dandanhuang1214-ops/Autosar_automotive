from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.can_io import BusConfig
from automotive_workbench.explanation_services import Endpoint, ServiceError, parse_json, retrieve
from automotive_workbench.model_explanation import (
    PROMPTS, constrained_answer_schema, exact_draft_schema, explain, extract_exact_draft, quote_options,
    is_exact_named_check_field_request, is_manual_applicability_request,
    required_complex_named_check_fact_ids,
    required_named_check_field_fact_ids, required_stage_status_fact_ids, select_facts,
    validate_bound_draft_literals, validate_draft, validate_exact_draft, verify_explanation,
)
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]


class StubEndpoint(Endpoint):
    mode = "normal"

    def request(self, path, payload=None):
        error = None
        if self.mode == "unavailable":
            value, error = None, "service_unavailable:URLError"
        elif path == "/api/version":
            value = {"version": "unit-fixture"}
        elif path == "/api/tags":
            value = {"models": [{"name": "fixture:1", "digest": "a" * 64}]}
        elif path == "/api/chat":
            context = json.loads(payload["messages"][1]["content"])
            fact = context["facts"][0]
            answer = {"request_id": context["request_id"], "status": "selected",
                      "project_claims": [{"fact_id": fact["fact_id"], "value": fact["value"]}],
                      "manual_claims": [], "draft_explanation": "unverified draft", "suggestions": []}
            if self.mode == "wrong_value":
                answer["project_claims"][0]["value"] = "passed"
            value = {"model": "fixture:1", "message": {"role": "assistant", "content": json.dumps(answer)}, "done": True, "done_reason": "stop", "prompt_eval_count": 1000, "eval_count": 100}
        else:
            raise AssertionError(path)
        self.records.append({"path": path, "method": "POST" if payload is not None else "GET", "payload": payload,
                             "http_status": None if error else 200, "raw": "" if error else json.dumps(value), "error": error})
        if error:
            raise ServiceError(error)
        return value


class ModelExplanationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = Path(run_project(ROOT / "examples/ecuc_diagnostic/integration.project.json", self.root / "project",
                                       BusConfig("virtual", "model-unit"))["report_json"])

    def run_model(self, mode="normal", name="explanation"):
        with patch.object(StubEndpoint, "mode", mode):
            return explain(self.report, "为什么阻断？", self.root / name, "fixture:1", _endpoint_factory=StubEndpoint)

    def test_preserves_verdict_and_replays_without_services(self):
        result = self.run_model()
        schemas = [json.loads((ROOT / "schemas" / name).read_text()) for name in (
            "project-model-explanation.schema.json", "project-explanation-request.schema.json")]
        registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
        Draft202012Validator(schemas[0], registry=registry).validate(result)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["project_status"], "blocked")
        self.assertEqual(result["answer"]["semantic_status"], "unassessed")
        self.assertEqual(result["model"]["digest"], "a" * 64)
        self.assertTrue(any(g["code"] == "PROJECT_EVIDENCE_GAP" for g in result["gaps"]))
        with patch.object(Endpoint, "request", side_effect=AssertionError("network forbidden")):
            self.assertEqual(verify_explanation(self.report, self.root / "explanation")["status"], "passed")
        for artifact in (self.root / "explanation").iterdir():
            self.assertNotIn(b"\r\n", artifact.read_bytes(), artifact.name)
        moved = self.root / "中文 move"
        self.report.parent.rename(moved)
        self.report = moved / self.report.name
        self.assertEqual(verify_explanation(self.report, self.root / "explanation")["status"], "passed")

    def test_unavailable_and_rejected_preserve_fallback_and_raw_records(self):
        for mode, expected in (("unavailable", "blocked"), ("wrong_value", "refused")):
            result = self.run_model(mode, mode)
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["project_status"], "blocked")
            self.assertTrue(result["fallback_facts"])
            self.assertIsNone(result["answer"])
            self.assertTrue((self.root / mode / "transport.json").is_file())
            self.assertEqual(verify_explanation(self.report, self.root / mode)["status"], "passed")

    def test_tampered_input_raw_result_and_extra_files_rejected(self):
        self.run_model()
        output = self.root / "explanation"
        for name in ("model-input.json", "raw-model-response.json", "explanation.json", "model-context.json"):
            file = output / name
            original = file.read_bytes()
            changed = json.loads(original)
            changed["unexpected"] = True
            file.write_text(json.dumps(changed))
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_explanation(self.report, output)
            file.write_bytes(original)
        (output / "extra.txt").write_text("extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify_explanation(self.report, output)

    def test_source_changes_during_generation_fail_closed_and_save_failure(self):
        import automotive_workbench.model_explanation as module
        real_build = module.build_request
        calls = 0
        def changing(*args):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise ValueError("source changed")
            return real_build(*args)
        with patch.object(module, "build_request", side_effect=changing):
            result = self.run_model()
        self.assertEqual(result["status"], "refused")
        self.assertFalse(result["fallback_facts"])
        self.assertIsNone(result["answer"])
        self.assertTrue((self.root / "explanation/transport.json").exists())

    def test_endpoint_and_json_boundaries(self):
        for origin in ("file:///tmp/x", "http://user:pass@localhost", "http://localhost/path", "http://localhost?x=1"):
            with self.assertRaises(ValueError):
                Endpoint(origin, 1)
        for timeout in (0, -1, float("nan"), float("inf"), 121):
            with self.assertRaises(ValueError):
                Endpoint("http://localhost", timeout)
        for raw in ('{"id":1,"id":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                parse_json(raw)

    def test_historical_prompt_versions_replay_with_original_payloads(self):
        for version in PROMPTS:
            output = self.root / version
            explain(self.report, "为什么阻断？", output, "fixture:1",
                    _endpoint_factory=StubEndpoint, _prompt_version=version)
            with self.subTest(version=version):
                self.assertEqual(verify_explanation(self.report, output)["status"], "passed")
                payload = json.loads((output / "model-input.json").read_text())
                context = json.loads(payload["messages"][1]["content"])
                if version in list(PROMPTS)[:4]:
                    self.assertIn("properties", payload["format"])
                    self.assertIn("source_sha256", context["facts"][0])
                    self.assertIs(payload["think"], False)
                    self.assertEqual(payload["options"]["num_predict"], 1600)
                else:
                    self.assertEqual(payload.get("think"), None)
                    self.assertEqual(payload["options"]["num_predict"], 4096)
                    self.assertEqual(payload["options"]["num_ctx"], 8192 if version.endswith(("0.7", "0.8", "0.9", "0.10", "0.11", "0.12", "0.13", "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22")) else 16384)
                    self.assertEqual(set(context["facts"][0]), {"fact_id", "artifact_id", "pointer", "value"})
                    expected_limit = 4000 if version.endswith(("0.5", "0.6")) else 160
                    for branch in payload["format"]["anyOf"]:
                        self.assertEqual(branch["properties"]["draft_explanation"]["maxLength"], expected_limit)
                    # Validate the generation boundary separately from the unchanged
                    # downstream semantic-unassessed contract.
                    draft_schema = payload["format"]["anyOf"][0]["properties"]["draft_explanation"]
                    validator = Draft202012Validator(draft_schema)
                    self.assertTrue(validator.is_valid("中" * expected_limit))
                    self.assertFalse(validator.is_valid("中" * (expected_limit + 1)))


    def test_v08_disables_thinking_only_for_verified_qwen3vl_family(self):
        class VisionEndpoint(StubEndpoint):
            def request(self, path, payload=None):
                if path == "/api/tags":
                    value = {"models": [{"name": "fixture:1", "digest": "a" * 64,
                                           "details": {"families": ["qwen3vl"]}}]}
                    self.records.append({"path": path, "method": "GET", "payload": None,
                                         "http_status": 200, "raw": json.dumps(value), "error": None})
                    return value
                if path == "/api/chat":
                    self.asserted_think = payload.get("think")
                return super().request(path, payload)
        with tempfile.TemporaryDirectory() as temporary:
            endpoint = VisionEndpoint("http://ollama:11434", 120)
            result = explain(self.report, "列出阻断原因", Path(temporary) / "vision", "fixture:1",
                             ollama_url="http://ollama:11434",
                             _endpoint_factory=lambda _url, _timeout: endpoint)
            self.assertEqual(endpoint.asserted_think, False)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(verify_explanation(self.report, Path(temporary) / "vision")["status"], "passed")
            saved = json.loads((Path(temporary) / "vision/model-input.json").read_text())
            self.assertIs(saved["think"], False)

    def test_v12_disables_thinking_for_verified_qwen35_family_only_in_new_version(self):
        class Qwen35Endpoint(StubEndpoint):
            def request(self, path, payload=None):
                if path == "/api/tags":
                    value = {"models": [{"name": "fixture:1", "digest": "a" * 64,
                                           "details": {"families": ["qwen35"]}}]}
                    self.records.append({"path": path, "method": "GET", "payload": None,
                                         "http_status": 200, "raw": json.dumps(value), "error": None})
                    return value
                if path == "/api/chat":
                    self.asserted_think = payload.get("think")
                return super().request(path, payload)

        with tempfile.TemporaryDirectory() as temporary:
            endpoint = Qwen35Endpoint("http://ollama:11434", 120)
            current = Path(temporary) / "current"
            result = explain(self.report, "列出阻断原因", current, "fixture:1",
                             ollama_url="http://ollama:11434",
                             _endpoint_factory=lambda _url, _timeout: endpoint)
            self.assertEqual(endpoint.asserted_think, False)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(verify_explanation(self.report, current)["status"], "passed")
            self.assertIs(json.loads((current / "model-input.json").read_text())["think"], False)

            historical_endpoint = Qwen35Endpoint("http://ollama:11434", 120)
            historical = Path(temporary) / "historical"
            result = explain(self.report, "列出阻断原因", historical, "fixture:1",
                             ollama_url="http://ollama:11434", _prompt_version="project-explanation-prompt-0.11",
                             _endpoint_factory=lambda _url, _timeout: historical_endpoint)
            self.assertIsNone(historical_endpoint.asserted_think)
            self.assertEqual(result["status"], "passed")
            self.assertNotIn("think", json.loads((historical / "model-input.json").read_text()))

    def test_v20_scopes_exact_named_check_fields_and_ignores_model_extras(self):
        class ExactEndpoint(StubEndpoint):
            def request(self, path, payload=None):
                if path != "/api/chat":
                    return super().request(path, payload)
                context = json.loads(payload["messages"][1]["content"])
                self.model_context = context
                literals = "；".join(str(fact["value"]) for fact in context["facts"])
                answer = {"request_id": context["request_id"], "draft_explanation": literals,
                          "status": "unassessed", "project_claims": [],
                          "manual_claims": [], "suggestions": []}
                value = {"model": "fixture:1", "message": {"role": "assistant", "content": json.dumps(answer)},
                         "done": True, "done_reason": "stop", "prompt_eval_count": 1000, "eval_count": 100}
                self.records.append({"path": path, "method": "POST", "payload": payload,
                                     "http_status": 200, "raw": json.dumps(value), "error": None})
                return value

        endpoint = ExactEndpoint("http://ollama:11434", 120)
        output = self.root / "exact-fields"
        result = explain(self.report, "diagnostic.read-version 的 status 和 reason 是什么？只引用这两个字段。",
                         output, "fixture:1", ollama_url="http://ollama:11434",
                         _endpoint_factory=lambda _url, _timeout: endpoint)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["reason"], "deterministic_requested_facts_model_prose_unverified")
        self.assertEqual(len(result["answer"]["project_facts"]), 2)
        self.assertEqual({fact["pointer"].rsplit("/", 1)[-1] for fact in endpoint.model_context["facts"]},
                         {"status", "reason"})
        self.assertNotIn("project_status", endpoint.model_context)
        self.assertEqual(endpoint.model_context["manuals"], [])
        self.assertIn("MODEL_FORMAT_EXTRAS_IGNORED", {gap["code"] for gap in result["gaps"]})
        self.assertEqual(verify_explanation(self.report, output)["status"], "passed")

    def test_v20_uses_compact_draft_contract_for_bound_complex_facts(self):
        class ComplexEndpoint(StubEndpoint):
            def request(self, path, payload=None):
                if path != "/api/chat":
                    return super().request(path, payload)
                context = json.loads(payload["messages"][1]["content"])
                self.model_context = context
                self.system_prompt = payload["messages"][0]["content"]
                literals = "；".join(str(fact["value"]) for fact in context["facts"])
                answer = {"request_id": context["request_id"], "draft_explanation": literals}
                value = {"model": "fixture:1", "message": {"role": "assistant", "content": json.dumps(answer)},
                         "done": True, "done_reason": "stop", "prompt_eval_count": 1000, "eval_count": 100}
                self.records.append({"path": path, "method": "POST", "payload": payload,
                                     "http_status": 200, "raw": json.dumps(value), "error": None})
                return value

        endpoint = ComplexEndpoint("http://ollama:11434", 120)
        output = self.root / "complex-fields"
        result = explain(
            self.report,
            "diagnostic.read-version 为何失败？请结合 status 和 reason 解释。",
            output,
            "fixture:1",
            ollama_url="http://ollama:11434",
            _endpoint_factory=lambda _url, _timeout: endpoint,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["answer"]["project_facts"]), 2)
        self.assertEqual(set(json.loads((output / "model-input.json").read_text())["format"]["anyOf"][0]["required"]),
                         {"request_id", "draft_explanation"})
        self.assertIn("exactly two keys", endpoint.system_prompt)
        self.assertIn("object identity, definition path and before/after value", endpoint.system_prompt)
        self.assertEqual(verify_explanation(self.report, output)["status"], "passed")

    def test_v21_manual_applicability_stays_unassessed_without_independent_review(self):
        class ManualGapEndpoint(StubEndpoint):
            def request(self, path, payload=None):
                if path != "/api/chat":
                    return super().request(path, payload)
                context = json.loads(payload["messages"][1]["content"])
                self.model_context = context
                answer = {"request_id": context["request_id"],
                          "draft_explanation": "资料适用性尚未独立审核，当前不能证明该标准要求。"}
                value = {"model": "fixture:1", "message": {"role": "assistant", "content": json.dumps(answer)},
                         "done": True, "done_reason": "stop", "prompt_eval_count": 1000, "eval_count": 100}
                self.records.append({"path": path, "method": "POST", "payload": payload,
                                     "http_status": 200, "raw": json.dumps(value), "error": None})
                return value

        endpoint = ManualGapEndpoint("http://ollama:11434", 120)
        output = self.root / "manual-gap"
        result = explain(
            self.report,
            "资料能否证明 AUTOSAR 标准要求该字段必须为 8？",
            output,
            "fixture:1",
            ollama_url="http://ollama:11434",
            _endpoint_factory=lambda _url, _timeout: endpoint,
        )
        self.assertEqual(result["status"], "unassessed")
        self.assertEqual(result["reason"], "manual_applicability_requires_human_review")
        self.assertEqual(result["answer"]["answer_status"], "unassessed")
        self.assertEqual(endpoint.model_context["facts"], [])
        self.assertNotIn("project_status", endpoint.model_context)
        self.assertEqual(verify_explanation(self.report, output)["status"], "passed")

    def test_v07_rejects_responses_that_overrun_recorded_context(self):
        class OversizedEndpoint(StubEndpoint):
            def request(self, path, payload=None):
                response = super().request(path, payload)
                if path == "/api/chat":
                    response["prompt_eval_count"] = 5000
                    response["eval_count"] = 4096
                return response
        with tempfile.TemporaryDirectory() as temporary:
            report = self.report
            result = explain(report, "为什么阻断？", Path(temporary) / "oversized", "fixture:1",
                             _endpoint_factory=OversizedEndpoint)
            self.assertEqual(result["status"], "refused")
            self.assertEqual(result["reason"], "invalid_or_exceeded_context_budget")
            self.assertIsNone(result["answer"])



class FactRetrievalTests(unittest.TestCase):
    @staticmethod
    def fact(pointer, value, artifact="stage-ecuc"):
        return {"fact_id": artifact + pointer, "artifact_id": artifact, "pointer": pointer, "value": value}

    def test_named_checks_survive_status_noise_and_keep_observation_distinct(self):
        facts = [self.fact(f"/checks/a{i}/status", "passed") for i in range(40)]
        wanted = [self.fact("/checks/policy.WIDTH/reason", "protected_field_changed"),
                  self.fact("/checks/runtime.packet-tx/reason", "static_acceptance_rejected")]
        facts += wanted + [self.fact("/checks/policy.WIDTH/observations/before/reason", "observed")]
        request = {"question": "WIDTH 为何拒绝？runtime.packet-tx 的 reason 是什么？", "facts": facts}
        selected = select_facts(request, 2)
        self.assertEqual({f["fact_id"] for f in selected}, {f["fact_id"] for f in wanted})
        self.assertEqual(selected, select_facts({**request, "facts": list(reversed(facts))}, 2))
        self.assertFalse(any(f in wanted for f in select_facts(request, 2, prompt_version="project-explanation-prompt-0.4")))

    def test_impact_identities_and_before_after_typed_values(self):
        facts = [self.fact(f"/checks/a{i}/reason", "observed") for i in range(40)]
        impact = [self.fact(f"/checks/impact/affected_objects/{i}", f"ecuc:/Other/{i}") for i in range(2)]
        facts += impact
        self.assertEqual(select_facts({"question": "impact 的影响对象身份有哪些？", "facts": facts}, 2), impact)
        values = [self.fact(f"/checks/policy.WIDTH/observations/{side}/values/0", value)
                  for side, value in (("before", 16), ("after", 24))]
        selected = select_facts({"question": "WIDTH 变更前和变更后的数值？", "facts": facts + values}, 2)
        self.assertEqual({f["fact_id"] for f in selected}, {f["fact_id"] for f in values})

    def test_v09_includes_requested_nested_binding_fields_and_named_stage_status(self):
        binding = [self.fact(f"/checks/diagnostic.read-version/binding/{field}", value)
                   for field, value in (("request_id", 42), ("response_id", 240), ("did", 52993))]
        other = [self.fact("/checks/other/status", "failed"),
                 self.fact("/checks/diagnostic.read-version/status", "blocked"),
                 self.fact("/checks/diagnostic.read-version/reason", "diagnostic_backend_mismatch")]
        question = "diagnostic.read-version 的 request_id、response_id 和 DID 是什么？"
        selected = select_facts({"question": question, "facts": binding + other})
        self.assertEqual({fact["pointer"] for fact in selected}, {fact["pointer"] for fact in binding})

        stage = self.fact("/stages/ecuc/status", "blocked", "project-report")
        stage_question = "ECUC 阶段状态是什么，diagnostic.read-version 的状态和 reason 是什么？"
        selected = select_facts({"question": stage_question, "facts": [stage, *other]})
        self.assertIn(stage, selected)
        self.assertIn(other[1], selected)
        self.assertIn(other[2], selected)
        self.assertNotIn(other[0], selected)

    def test_v10_scopes_status_only_questions_to_report_and_named_stage(self):
        facts = [self.fact("/status", "passed", "project-report"),
                 self.fact("/stages/ecuc/status", "passed", "project-report")]
        facts += [self.fact(f"/checks/check-{i}/status", "failed") for i in range(30)]
        question = "Give overall project status and ECUC stage status only."
        selected = select_facts({"question": question, "facts": facts}, prompt_version="project-explanation-prompt-0.10")
        self.assertEqual({fact["fact_id"] for fact in selected}, {fact["fact_id"] for fact in facts[:2]})

        historical = select_facts({"question": question, "facts": facts}, prompt_version="project-explanation-prompt-0.9")
        self.assertGreater(len(historical), len(selected))

    def test_v11_requires_complete_claims_for_overall_and_stage_status(self):
        question = "Give overall project status and ECUC stage status only."
        facts = [self.fact("/status", "unassessed", "project-report"),
                 self.fact("/stages/ecuc/status", "unassessed", "project-report")]
        required = required_stage_status_fact_ids(question, facts)
        self.assertEqual(required, {fact["fact_id"] for fact in facts})
        self.assertEqual(required_stage_status_fact_ids(question, facts,
                                                        prompt_version="project-explanation-prompt-0.11"), required)
        self.assertIsNone(required_stage_status_fact_ids(question, facts,
                                                         prompt_version="project-explanation-prompt-0.10"))

        context = {"request_id": "request", "facts": facts, "manuals": []}
        answer = {"request_id": "request", "status": "selected",
                  "project_claims": [{"fact_id": facts[1]["fact_id"], "value": "unassessed"}],
                  "manual_claims": [],
                  "draft_explanation": "Both statuses are unassessed.", "suggestions": []}
        with self.assertRaisesRegex(ValueError, "required_project_claims_incomplete"):
            validate_draft(answer, context, required_project_fact_ids=required)

        answer["project_claims"] = [{"fact_id": fact["fact_id"], "value": fact["value"]} for fact in facts]
        validated = validate_draft(answer, context, required_project_fact_ids=required)
        self.assertEqual(len(validated["project_facts"]), 2)

        schema = constrained_answer_schema("request", facts, [], minimum_project_claims=2, require_selected=True)
        self.assertEqual(len(schema["anyOf"]), 1)
        self.assertEqual(schema["anyOf"][0]["properties"]["project_claims"]["minItems"], 2)

    def test_v13_requires_all_named_check_fields_and_excludes_unrequested_sources(self):
        question = ("runtime.signal-tx 和 runtime.signal-rx 的 status 与 reason 分别是什么？"
                    "只引用这四项字段。")
        facts = [self.fact("/status", "unassessed", "project-report")]
        facts += [self.fact(f"/checks/{check}/{field}", value)
                  for check, status, reason in (("runtime.signal-tx", "unassessed", "frame_id_mismatch"),
                                                ("runtime.signal-rx", "unassessed", "another_binding_rejected"))
                  for field, value in (("status", status), ("reason", reason))]
        required = required_named_check_field_fact_ids(question, facts)
        self.assertEqual(required, {fact["fact_id"] for fact in facts[1:]})
        self.assertIsNone(required_named_check_field_fact_ids(
            question, facts, prompt_version="project-explanation-prompt-0.12"))

        manuals = [{"source_id": "manual", "excerpt": "Unrelated retrieved text."}]
        schema = constrained_answer_schema("request", facts, manuals, minimum_project_claims=4,
                                           require_selected=True, exact_project_fact_ids=required)
        Draft202012Validator.check_schema(schema)
        properties = schema["anyOf"][0]["properties"]
        self.assertEqual(properties["project_claims"]["minItems"], 4)
        self.assertEqual(properties["project_claims"]["maxItems"], 4)
        self.assertEqual(properties["manual_claims"]["enum"], [[]])
        self.assertEqual(properties["suggestions"]["enum"], [[]])
        allowed_ids = {item["fact_id"] for item in properties["project_claims"]["items"]["enum"]}
        self.assertEqual(allowed_ids, required)

        answer = {"request_id": "request", "status": "selected",
                  "project_claims": [{"fact_id": fact["fact_id"], "value": fact["value"]}
                                     for fact in facts[1:]],
                  "manual_claims": [], "draft_explanation": "四项字段均按记录复述。", "suggestions": []}
        Draft202012Validator(schema).validate(answer)
        context = {"request_id": "request", "facts": facts, "manuals": manuals}
        self.assertEqual(len(validate_draft(answer, context,
                                            required_project_fact_ids=required)["project_facts"]), 4)

        draft_schema = exact_draft_schema("request")
        Draft202012Validator.check_schema(draft_schema)
        draft = {"request_id": "request", "draft_explanation": "仅解释记录字段。"}
        Draft202012Validator(draft_schema).validate(draft)
        self.assertEqual(validate_exact_draft(draft, "request"), draft["draft_explanation"])
        with self.assertRaisesRegex(ValueError, "wrong_exact_draft_contract_or_request"):
            validate_exact_draft({**draft, "status": "selected"}, "request")
        legacy = {**draft, "status": "unassessed", "project_claims": [],
                  "manual_claims": [], "suggestions": []}
        self.assertEqual(extract_exact_draft(legacy, "request"), (draft["draft_explanation"], True))
        self.assertEqual(extract_exact_draft(draft, "request"), (draft["draft_explanation"], False))

    def test_v18_binds_rich_named_check_context_and_preserves_v17_routing(self):
        question = ("policy.SIGNAL_SIZE 检查为何失败？请结合检查 status、reason、对象身份、"
                    "字段定义以及 before/after values 解释记录中的变化。")
        facts = [self.fact("/status", "failed", "project-report")]
        facts += [self.fact(pointer, value) for pointer, value in (
            ("/checks/policy.SIGNAL_SIZE/status", "failed"),
            ("/checks/policy.SIGNAL_SIZE/reason", "protected_field_changed"),
            ("/checks/policy.SIGNAL_SIZE/policy/object_id", "ecuc:/Demo/Com/ValueA"),
            ("/checks/policy.SIGNAL_SIZE/policy/definition", "/Synthetic/ComSignal/ComBitSize"),
            ("/checks/policy.SIGNAL_SIZE/observations/before/values/0", "8"),
            ("/checks/policy.SIGNAL_SIZE/observations/after/values/0", "12"),
            ("/checks/policy.SIGNAL_SIZE/observations/before/path", "before.json"),
        )]
        selected = select_facts({"question": question, "facts": facts})
        selected_pointers = {fact["pointer"] for fact in selected}
        self.assertTrue({fact["pointer"] for fact in facts[1:7]} <= selected_pointers)
        self.assertFalse(is_exact_named_check_field_request(question))
        self.assertEqual(required_complex_named_check_fact_ids(question, selected),
                         {fact["fact_id"] for fact in facts[1:7]})
        self.assertIsNone(required_complex_named_check_fact_ids(
            question, selected, prompt_version="project-explanation-prompt-0.17"))
        self.assertEqual(required_complex_named_check_fact_ids(
            question, selected, prompt_version="project-explanation-prompt-0.18"),
            {fact["fact_id"] for fact in facts[1:7]})
        self.assertTrue(is_exact_named_check_field_request(
            "policy.SIGNAL_SIZE 的 status 和 reason 是什么？只引用这两个字段。"))
        self.assertFalse(is_exact_named_check_field_request(
            question, prompt_version="project-explanation-prompt-0.17"))
        self.assertTrue(is_exact_named_check_field_request(
            question, prompt_version="project-explanation-prompt-0.16"))

    def test_v18_scopes_missing_identity_and_values_to_the_requested_checks(self):
        question = ("为什么不能概括为全部失败？对比 policy.SIGNAL_PRESENT 与 policy.SIGNAL_SIZE "
                    "的 status/reason，指出缺失对象身份，并给出 SIGNAL_SIZE 的 before/after values。")
        facts = [self.fact(pointer, value) for pointer, value in (
            ("/checks/policy.SIGNAL_PRESENT/status", "failed"),
            ("/checks/policy.SIGNAL_PRESENT/reason", "missing_object"),
            ("/checks/policy.SIGNAL_PRESENT/policy/object_id", "ecuc:/Demo/Com/Absent"),
            ("/checks/policy.SIGNAL_SIZE/status", "passed"),
            ("/checks/policy.SIGNAL_SIZE/reason", "protected_field_unchanged"),
            ("/checks/policy.SIGNAL_SIZE/policy/object_id", "ecuc:/Demo/Com/ValueA"),
            ("/checks/policy.SIGNAL_SIZE/observations/before/values/0", "8"),
            ("/checks/policy.SIGNAL_SIZE/observations/after/values/0", "8"),
            ("/checks/policy.SIGNAL_PRESENT/observations/before/values/0", "missing"),
            ("/checks/policy.SIGNAL_PRESENT/observations/after/values/0", "missing"),
        )]
        required = required_complex_named_check_fact_ids(question, facts)
        self.assertEqual(required, {facts[index]["fact_id"] for index in (0, 1, 2, 3, 4, 6, 7)})

    def test_v20_manual_applicability_scope_and_bound_literal_guard(self):
        question = "资料能否证明 AUTOSAR 标准要求这个值必须为 8？"
        self.assertTrue(is_manual_applicability_request(question))
        self.assertFalse(is_manual_applicability_request(
            question, prompt_version="project-explanation-prompt-0.19"))
        facts = [self.fact("/checks/policy.SIZE/status", "failed"),
                 self.fact("/checks/policy.SIZE/reason", "protected_field_changed"),
                 self.fact("/checks/policy.SIZE/policy/object_id", "ecuc:/Demo/Com/ValueA")]
        self.assertEqual(
            validate_bound_draft_literals("对象为 ecuc:/Demo/Com/ValueA。", facts),
            "对象为 ecuc:/Demo/Com/ValueA。",
        )
        with self.assertRaisesRegex(ValueError, "required_fact_values_missing_from_draft"):
            validate_bound_draft_literals("检查失败，但没有复述记录原因。", facts)

    def test_context_budget_and_no_fabricated_facts(self):
        facts = [self.fact("/checks/impact/affected_objects/0", "x" * 13000), self.fact("/status", "failed", "project-report")]
        self.assertEqual(select_facts({"question": "影响", "facts": facts}), facts[1:])
        self.assertEqual(select_facts({"question": "物理 ECU 已验证吗？", "facts": []}), [])

    def test_schema_binds_pairs_quotes_and_unassessed_empty_lists(self):
        facts = [self.fact("/a", 7), self.fact("/b", {"items": [False, 2]})]
        manual = {"source_id": "manual", "excerpt": "Timeout alone is inconclusive.\nInspect recorded conditions."}
        schema = constrained_answer_schema("request", facts, [manual])
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        answer = {"request_id": "request", "status": "selected", "project_claims": [
            {"fact_id": facts[1]["fact_id"], "value": facts[1]["value"]}],
            "manual_claims": [{"source_id": "manual", "quote": quote_options(manual)[0]}],
            "draft_explanation": "draft", "suggestions": []}
        validator.validate(answer)
        for changed in ({**answer, "status": "unassessed"},
                        {**answer, "project_claims": [{"fact_id": facts[0]["fact_id"], "value": facts[1]["value"]}]},
                        {**answer, "manual_claims": [{"source_id": "manual", "quote": "ECU passed"}]}):
            self.assertFalse(validator.is_valid(changed))
        validator.validate({**answer, "status": "unassessed", "project_claims": [], "manual_claims": []})
        for quote in quote_options(manual):
            self.assertIn(quote, manual["excerpt"])


class IndependentDraftContractTests(unittest.TestCase):
    """Independent value/citation cases; no model quality or held-out LLM claim."""
    def setUp(self):
        self.context = {"request_id": "request", "facts": [{"fact_id": "f1", "value": 1},
                        {"fact_id": "f2", "value": "error"}, {"fact_id": "f3", "value": "ecuc:/Demo/Object"}],
                        "manuals": [{"source_id": "m1", "excerpt": "Timeout has multiple possible causes."}]}
        self.good = {"request_id": "request", "status": "selected", "project_claims": [{"fact_id": "f1", "value": 1}],
                     "manual_claims": [{"source_id": "m1", "quote": "multiple possible causes"}],
                     "draft_explanation": "draft", "suggestions": []}

    def test_numeric_severity_object_and_cross_namespace_rejection(self):
        variants = [("f1", True), ("f1", 1.0), ("f2", "warning"), ("f3", "ecuc:/Other/Object"), ("m1", 1)]
        for identity, value in variants:
            answer = {**self.good, "project_claims": [{"fact_id": identity, "value": value}]}
            with self.subTest(identity=identity, value=value), self.assertRaises(ValueError):
                validate_draft(answer, self.context)

    def test_quote_request_and_suggestion_binding(self):
        cases = [{**self.good, "request_id": "old"},
                 {**self.good, "manual_claims": [{"source_id": "f1", "quote": "multiple"}]},
                 {**self.good, "manual_claims": [{"source_id": "m1", "quote": "Project passed"}]},
                 {**self.good, "suggestions": [{"text": "Check", "fact_ids": ["bad"]}]}]
        for answer in cases:
            with self.assertRaises(ValueError):
                validate_draft(answer, self.context)
        draft = copy.deepcopy(self.good)
        draft["draft_explanation"] = "Unsupported physical ECU certification claim"
        draft["suggestions"] = [{"text": "Check wiring", "fact_ids": ["f1"]}]
        result = validate_draft(draft, self.context)
        self.assertEqual(result["semantic_status"], "unassessed")
        self.assertEqual(result["suggestions"][0]["execution_status"], "not_executed")

    def test_knowledge_requires_reviewed_current_content(self):
        endpoint = Endpoint("http://localhost", 1)
        item = {"chunk_id": 10, "document_id": 1, "content": "Recorded text", "page": 1, "title": "Manual"}
        doc = {"id": 1, "enabled": True, "status": "ready", "review_status": "approved", "authority": "official", "sha256": "a" * 64}
        for bad_doc, detail in (({**doc, "review_status": "pending"}, item), ({**doc, "authority": "ai_draft"}, item), (doc, {**item, "content": "Changed"})):
            with patch.object(endpoint, "request", side_effect=[{"query": "q", "results": [item]}, [bad_doc], detail]):
                with self.assertRaises(ServiceError):
                    retrieve(endpoint, "q")
