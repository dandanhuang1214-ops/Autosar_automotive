from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assess_model_explanation import assess, bundle_digest, gold_ids, resolve, score, write
from automotive_workbench.project_explanation import digest


class ModelAssessmentTests(unittest.TestCase):
    def test_guard_rejection_does_not_count_as_model_refusal(self):
        case = {"gold_fact_ids": []}
        context = {"facts": [], "manuals": []}
        result = {"status": "refused", "reason": "invalid_citation", "answer": None, "elapsed_ms": 1, "gaps": []}
        rejected = score(case, result, context)
        self.assertFalse(rejected["model_declared_insufficient"])
        self.assertFalse(rejected["structured_task_passed"])
        self.assertIsNone(rejected["gold_recall"])
        result.update(status="unassessed", answer={"answer_status": "unassessed"})
        self.assertTrue(score(case, result, context)["model_declared_insufficient"])

    def test_context_omission_separate_from_citation_and_semantics(self):
        case = {"gold_fact_ids": ["a", "b"]}
        context = {"facts": [{"fact_id": "a"}], "manuals": [{"source_id": "m"}]}
        result = {"status": "passed", "reason": "valid", "elapsed_ms": 1, "gaps": [],
                  "answer": {"project_facts": [{"fact_id": "a"}], "manual_quotes": [{"source_id": "m"}]}}
        measured = score(case, result, context)
        self.assertEqual(measured["context_facts"], 1)
        self.assertEqual(measured["gold_recall"], 0.5)
        self.assertFalse(measured["structured_task_passed"])
        self.assertEqual(measured["prose_correctness"], "unassessed")
        self.assertEqual(measured["manual_relevance"], "unassessed")

    def test_gold_distinguishes_type_and_object(self):
        request = {"facts": [{"fact_id": "a", "artifact_id": "x", "pointer": "/count", "value": 1}]}
        with self.assertRaises(ValueError):
            gold_ids(request, [{"artifact_id": "x", "pointer": "/count", "value": True}])
        with self.assertRaises(ValueError):
            gold_ids(request, [{"artifact_id": "y", "pointer": "/count", "value": 1}])

    def test_frozen_evidence_mutation_stops_before_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            bundle.mkdir()
            report = bundle / "report.json"
            write(report, {"status": "failed"})
            manifest = {"implementation_sha256": "code", "cases": [
                {"id": "case", "report": "bundle/report.json", "bundle_sha256": bundle_digest(report)}]}
            path = root / "frozen.json"
            write(path, manifest)
            write(report, {"status": "passed"})
            with patch("scripts.assess_model_explanation.implementation_digest", return_value="code"), \
                    patch("scripts.assess_model_explanation.explain") as model:
                with self.assertRaisesRegex(ValueError, "Frozen evidence changed"):
                    assess(root, path, digest(manifest), root / "out", "http://localhost:1", None)
                model.assert_not_called()
                with self.assertRaisesRegex(ValueError, "Frozen manifest"):
                    assess(root, path, "wrong", root / "out", "http://localhost:1", None)
            with self.assertRaises(ValueError):
                resolve(root, "../escape")
