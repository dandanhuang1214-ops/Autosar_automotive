from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.review_eval import (
    load_evaluation_manifest,
    run_review_evaluation,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "review" / "evaluation" / "evaluation.json"


class ReviewEvaluationTests(unittest.TestCase):
    def test_gold_evaluation_meets_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(MANIFEST, output)
            persisted = json.loads(
                (output / "review-evaluation.json").read_text(encoding="utf-8")
            )
            markdown = (output / "review-evaluation.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["case_count"], 10)
        self.assertEqual(result["repeat_runs"], 3)
        self.assertTrue(all(case["passed"] for case in result["cases"]))
        self.assertEqual(result["metrics"]["false_conflict_count"], 0)
        self.assertTrue(
            all(
                value == 1.0
                for key, value in result["metrics"].items()
                if key != "false_conflict_count"
            )
        )
        self.assertEqual(persisted["schema_version"], "review-evaluation-result-0.1")
        self.assertIn("does not use an LLM judge", markdown)

    def test_rejects_duplicate_evaluation_case(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"].append(manifest["cases"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate.*case_id"):
                load_evaluation_manifest(path)


if __name__ == "__main__":
    unittest.main()
