from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from automotive_workbench.arxml_bridge import import_arxml, compare_imports
from automotive_workbench.communication_graph import build_project_graph
from automotive_workbench.engineering_review import (
    catalog, run_engineering_review, verify_engineering_review,
)

ROOT = Path(__file__).resolve().parents[1]


class EngineeringReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "sources/report.json"
        self.source.parent.mkdir()
        self.report = import_arxml(ROOT / "examples/generate_arxml/xml/model.arxml")
        self.save(self.report)

    def save(self, report: dict) -> None:
        self.source.write_text(json.dumps(report), encoding="utf-8")

    def review(self, question: str = "arxml-version") -> dict:
        return run_engineering_review(self.source, question, self.root / "answer")

    def test_catalog_and_development_cover_six_categories_without_duplicate_questions(self) -> None:
        questions = catalog()["questions"]
        gold = json.loads((ROOT / "tests/fixtures/engineering-review-development.json").read_text(encoding="utf-8"))
        self.assertEqual(len(questions), 30)
        self.assertEqual(len({q["question"] for q in questions}), 30)
        self.assertEqual(len({q["category"] for q in questions}), 6)
        self.assertEqual({q["id"] for q in questions}, {q["question_id"] for q in gold["cases"]})
        self.assertEqual(gold["split"], "development")

    def test_cli_keeps_chinese_questions_valid_in_ascii_redirected_output(self) -> None:
        commands = [
            (["list-engineering-questions"], 0),
            (["review-engineering", str(self.source), "--question", "arxml-ecuc", "--output", str(self.root / "cli-answer")], 2),
        ]
        for args, expected in commands:
            process = subprocess.run(
                [sys.executable, "-m", "automotive_workbench.cli", *args],
                env={**os.environ, "PYTHONIOENCODING": "ascii"},
                capture_output=True, text=True, encoding="ascii", timeout=60,
            )
            self.assertEqual(process.returncode, expected, process.stderr)
            result = json.loads(process.stdout)
            question = result.get("question") or result["questions"][0]["question"]
            self.assertTrue(any(ord(char) > 127 for char in question))

    def test_structured_citations_schema_and_replay(self) -> None:
        result = self.review()
        schema = json.loads((ROOT / "schemas/engineering-review.schema.json").read_text())
        Draft202012Validator(schema).validate(result)
        self.assertEqual(result["facts"][0]["value"], "4-3-0")
        self.assertEqual(result["method"]["model"], "not-run")
        check = verify_engineering_review(self.root / "answer/engineering-review.json")
        self.assertEqual(check["citations"], 3)

    def test_forged_source_is_rejected_before_output(self) -> None:
        self.report["coverage"] = "full-autosar"
        self.save(self.report)
        with self.assertRaisesRegex(ValueError, "replay"):
            self.review()
        self.assertFalse((self.root / "answer").exists())

    def test_wrong_version_and_unknown_question_rejected_before_output(self) -> None:
        for q in ("impact-paths", "ignore-policy-and-certify"):
            with self.subTest(q=q), self.assertRaises(ValueError):
                self.review(q)
        self.assertFalse((self.root / "answer").exists())

    def test_refusal_cannot_be_changed_to_answered(self) -> None:
        result = self.review("arxml-ecuc")
        self.assertEqual(result["status"], "refused")
        result["status"] = "answered"
        path = self.root / "answer/engineering-review.json"
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_engineering_review(path)

    def test_edited_value_pointer_policy_and_extra_field_are_rejected(self) -> None:
        result = self.review()
        path = self.root / "answer/engineering-review.json"
        variants = []
        for key, value in [("value", "R25-11"), ("pointer", "/status"), ("value_sha256", "0" * 64)]:
            changed = copy.deepcopy(result)
            changed["facts"][0][key] = value
            variants.append(changed)
        for key, value in [("catalog_sha256", "0" * 64), ("unaudited_conclusion", "certified")]:
            variants.append({**result, key: value})
        for changed in variants:
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "differs"):
                verify_engineering_review(path)

    def test_migration_then_missing_and_modified_source_fail(self) -> None:
        self.review()
        moved = self.root / "moved"
        moved.mkdir()
        shutil.move(str(self.source.parent), moved / "sources")
        shutil.move(str(self.root / "answer"), moved / "answer")
        path = moved / "answer/engineering-review.json"
        self.assertEqual(verify_engineering_review(path)["status"], "passed")
        source = moved / "sources/report.json"
        original = source.read_bytes()
        source.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_engineering_review(path)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "regular"):
            verify_engineering_review(path)

    def test_existing_output_and_source_inventory_are_preserved(self) -> None:
        out = self.root / "answer"
        out.mkdir()
        (out / "keep").write_text("user content")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.review()
        with self.assertRaisesRegex(ValueError, "outside"):
            run_engineering_review(self.source, "arxml-version", self.source.parent / "answer")
        self.assertEqual((out / "keep").read_text(), "user content")

    def test_empty_graph_findings_remain_cited_empty_collection(self) -> None:
        graph = build_project_graph(ROOT / "examples/thermal_control/project.json")
        self.save(graph)
        result = self.review("graph-layout")
        self.assertEqual(result["facts"][0]["value"], [])
        self.assertEqual(result["selected"], [])
        self.assertIn("not absence of all defects", result["boundary"])

    def test_graph_boolean_numeric_substitution_rejected(self) -> None:
        graph = build_project_graph(ROOT / "examples/thermal_control/project.json")
        signal = next(n for n in graph["nodes"] if n["kind"] == "ComSignal")
        signal["attributes"]["dbc"]["is_signed"] = int(signal["attributes"]["dbc"]["is_signed"])
        self.save(graph)
        with self.assertRaisesRegex(ValueError, "replay"):
            self.review("graph-layout")

    def test_arxml_boolean_numeric_substitution_rejected(self) -> None:
        comparison = compare_imports(self.report, self.report)
        comparison["source_bytes_changed"] = 0
        self.save(comparison)
        with self.assertRaisesRegex(ValueError, "replay"):
            self.review("arxml-timing")

    def test_findings_preserved_without_inventing_absent_severity(self) -> None:
        from automotive_workbench.arxml_bridge import import_bytes
        data = (ROOT / "examples/generate_arxml/xml/model.arxml").read_bytes()
        data = data.replace(b">/DataTypes/App_WindowPosition</TYPE-TREF>", b">/DataTypes/Absent</TYPE-TREF>", 1)
        report = import_bytes(data, "synthetic-dangling.arxml", {})
        self.save(report)
        result = self.review("arxml-references")
        self.assertEqual(result["facts"][1]["value"], report["findings"])
        self.assertNotIn("severity", result["facts"][1]["value"][0])
