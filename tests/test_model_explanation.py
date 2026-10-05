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
from automotive_workbench.model_explanation import explain, validate_draft, verify_explanation
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
            value = {"model": "fixture:1", "message": {"role": "assistant", "content": json.dumps(answer)}, "done": True, "done_reason": "stop"}
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
