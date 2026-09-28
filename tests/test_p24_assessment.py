from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from automotive_workbench.engineering_review import canonical, catalog, digest
from automotive_workbench.engineering_search import search_questions
from automotive_workbench.review import run_review, validate_citations
from scripts.run_p24_assessment import assertions, mutate, verify_seal

ROOT = Path(__file__).resolve().parents[1]


class P24AssessmentTests(unittest.TestCase):
    def test_navigation_matches_chinese_and_english_without_answering_claims(self) -> None:
        schema = json.loads((ROOT / "schemas/engineering-question-search.schema.json").read_text())
        for text, expected in [("信号布局冲突", "graph-layout"), ("arxml version", "arxml-version"), ("物理 ECU 量产通过", "source-physical")]:
            result = search_questions(text, 3)
            Draft202012Validator(schema).validate(result)
            self.assertEqual(result["candidates"][0]["question_id"], expected)
            self.assertNotEqual(result["status"], "answered")
            self.assertNotIn("facts", result)
        self.assertEqual(result["candidates"][0]["policy"], "scope-refusal")

    def test_version_filter_no_match_and_stable_order(self) -> None:
        result = search_questions("XML 引用", 5, "arxml-import-0.1")
        self.assertTrue(result["candidates"])
        self.assertTrue(all(c["input_version"] == "arxml-import-0.1" for c in result["candidates"]))
        self.assertEqual(result, search_questions("XML 引用", 5, "arxml-import-0.1"))
        self.assertEqual(search_questions("齿轮润滑油粘度")["status"], "no-match")
        self.assertEqual(search_questions("🛠")["status"], "no-match")

    def test_invalid_navigation_bounds_and_frozen_catalog(self) -> None:
        for query, limit, version in [(" ", 5, None), ("x" * 513, 5, None), ("a", True, None), ("a", 11, None), ("a", 1, "unknown")]:
            with self.subTest(query=query), self.assertRaises(ValueError):
                search_questions(query, limit, version)
        self.assertEqual(digest(canonical(catalog()).encode()), "428427a19e16d60bf613ae51a3b1718cce553401ab4cfeee47d3fd90a2351fde")

    def test_severity_summary_cannot_be_downgraded_omitted_or_invented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = {"findings": [{"code": "TEST-FINDING", "severity": "ERROR", "message": "Real recorded test finding", "source_artifact": "source.json"}]}
            (root / "source.json").write_text(json.dumps(evidence))
            request = {"schema_version": "review-request-0.2", "request_id": "severity-test", "question": "Recorded severity?", "minimum_coverage": 1, "allowed_confidentiality": ["public"],
                       "artifact_registry": [{"artifact_id": "source", "artifact_type": "test", "source": "source.json", "confidentiality": "public", "expected_sha256": digest((root / "source.json").read_bytes())}], "artifact_ids": ["source"],
                       "checks": [{"check_id": "severity", "statement": "Recorded severity is ERROR", "terms": ["severity"], "assertion": {"claim_key": "severity", "operator": "equals", "expected": "ERROR", "observations": [{"artifact_id": "source", "locator": {"type": "json-pointer", "pointer": "/findings/0/severity"}}]}}]}
            path = root / "request.json"
            path.write_text(json.dumps(request))
            result = run_review(path, root / "result")
            self.assertEqual(result["status"], "answered")
            for replacement in [[], [{**evidence["findings"][0], "severity": "WARNING"}], [*evidence["findings"], {**evidence["findings"][0], "code": "INVENTED"}]]:
                forged = {**result, "findings": replacement}
                self.assertEqual(forged["citations"], result["citations"])
                check = validate_citations(path, forged)
                self.assertEqual(check["status"], "failed")
                self.assertIn("including severity", check["reasons"][-1]["message"])

    def test_strong_gold_catches_missing_object_and_numeric_type_drift(self) -> None:
        gold = [{"pointer": "/objects", "operator": "project", "fields": ["id"], "value": [["signal"], ["route"]]}, {"pointer": "/value", "operator": "equals", "value": 1}]
        result = {"objects": [{"id": "signal"}, {"id": "route"}], "value": 1}
        self.assertTrue(assertions(result, gold))
        self.assertFalse(assertions({**result, "value": True}, gold))
        self.assertFalse(assertions({**result, "objects": [{"id": "signal"}]}, gold))

    def test_seal_detects_file_changes_and_unlisted_runtime_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            source = root / "src/a.py"
            source.write_text("# frozen\n")
            manifest = {"freeze": {"files": {"src/a.py": digest(source.read_bytes())}, "catalog_sha256": digest(canonical(catalog()).encode())}}
            with patch("scripts.run_p24_assessment.ROOT", root):
                verify_seal(manifest)
                source.write_text("# changed\n")
                with self.assertRaisesRegex(ValueError, "changed"):
                    verify_seal(manifest)
                source.write_text("# frozen\n")
                (root / "src/extra.py").write_text("# extra\n")
                with self.assertRaisesRegex(ValueError, "inventory"):
                    verify_seal(manifest)

    def test_fixture_mutations_are_confined_to_generated_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "case"
            source.mkdir()
            report = source / "report.json"
            report.write_text('{"x": [1, 2]}')
            outside = root / "keep.json"
            outside.write_text("{}")
            mutate(source, report, [{"op": "remove", "file": "$report", "pointer": "/x/0"}])
            self.assertEqual(json.loads(report.read_text()), {"x": [2]})
            with self.assertRaisesRegex(ValueError, "escapes"):
                mutate(source, report, [{"op": "delete_file", "file": "../keep.json"}])
            self.assertTrue(outside.exists())
