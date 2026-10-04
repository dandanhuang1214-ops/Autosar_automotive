from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from automotive_workbench.can_io import BusConfig
from automotive_workbench.project_explanation import build_request, prepare, validate_answer
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]


class ProjectExplanationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = Path(run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            self.root / "project", BusConfig("virtual", "explanation"),
        )["report_json"])
        self.request_path = self.root / "request.json"
        prepare(self.report, "哪些证据说明项目未通过？", self.request_path)
        self.request = json.loads(self.request_path.read_text(encoding="utf-8"))
        fact = self.request["facts"][0]
        self.answer = {"schema_version": "project-explanation-answer-0.1",
                       "request_id": self.request["request_id"], "status": "selected",
                       "claims": [{"fact_id": fact["fact_id"], "value": fact["value"]}]}

    def check_answer(self, answer=None):
        path = self.root / "answer.json"
        path.write_text(json.dumps(self.answer if answer is None else answer), encoding="utf-8")
        return validate_answer(self.report, self.request_path, path)

    def test_portable_closed_contract_and_status_preservation(self):
        for name, payload in (("request", self.request), ("answer", self.answer)):
            schema = json.loads((ROOT / f"schemas/project-explanation-{name}.schema.json").read_text())
            Draft202012Validator(schema).validate(payload)
        result = self.check_answer()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["project_status"], "blocked")
        self.assertEqual(result["facts"][0]["value"], "blocked")
        moved = self.root / "搬移 with spaces"
        shutil.move(self.report.parent, moved)
        self.report = moved / self.report.name
        self.assertEqual(self.check_answer(), result)

    def test_rejects_invalid_citation_status_prose_and_empty_selection(self):
        variants = []
        for field, value in (("fact_id", "0" * 64), ("value", "passed")):
            answer = copy.deepcopy(self.answer)
            answer["claims"][0][field] = value
            variants.append(answer)
        variants.extend([
            {**self.answer, "explanation": "Physical ECU acceptance passed"},
            {**self.answer, "claims": []},
            {**self.answer, "status": "unassessed"},
            {**self.answer, "claims": self.answer["claims"] * 2},
            {**self.answer, "request_id": "0" * 64},
        ])
        for answer in variants:
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                self.check_answer(answer)
        result = self.check_answer({**self.answer, "status": "unassessed", "claims": []})
        self.assertEqual(result["answer_status"], "unassessed")

    def test_preserves_numeric_types_and_object_identity(self):
        numeric = next(f for f in self.request["facts"] if type(f["value"]) is int)
        claim = {"fact_id": numeric["fact_id"], "value": numeric["value"]}
        answer = {**self.answer, "claims": [claim]}
        self.assertEqual(self.check_answer(answer)["facts"][0]["value"], numeric["value"])
        for value in (True, float(numeric["value"]), str(numeric["value"]), numeric["value"] + 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "does not match"):
                self.check_answer({**answer, "claims": [{**claim, "value": value}]})
        identity = next(f for f in self.request["facts"] if f["pointer"].endswith("/policy/object_id"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.check_answer({**answer, "claims": [{"fact_id": identity["fact_id"], "value": "/Different/Object"}]})

    def test_rejects_modified_request_and_historical_run(self):
        self.request["facts"][0]["value"] = "passed"
        self.request_path.write_text(json.dumps(self.request), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.check_answer()
        self.request_path.unlink()
        prepare(self.report, "why", self.request_path)
        self.report = Path(run_project(
            ROOT / "examples/ecuc_diagnostic/integration.project.json",
            self.root / "second", BusConfig("virtual", "explanation"),
        )["report_json"])
        with self.assertRaisesRegex(ValueError, "differs"):
            self.check_answer()

    def test_rejects_tampered_dependency_before_export(self):
        stage = self.report.parent / "ecuc-stage.json"
        payload = json.loads(stage.read_text())
        payload["status"] = "passed"
        stage.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            build_request(self.report, "why")

    def test_rejects_duplicate_json_keys_and_output_overwrite(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            prepare(self.report, "why", self.request_path)
        path = self.root / "duplicate.json"
        path.write_text('{"status":"selected","status":"unassessed"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_answer(self.report, self.request_path, path)


if __name__ == "__main__":
    unittest.main()
