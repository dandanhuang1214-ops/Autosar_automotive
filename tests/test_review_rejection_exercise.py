from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.review_eval import run_review_evaluation
from scripts.review_rejection_exercise import check_rejection, prepare_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT / "examples" / "review" / "evaluation"
    / "external-cohort-evaluation.json"
)


class ReviewRejectionExerciseTests(unittest.TestCase):
    def test_controlled_cli_failure_contract_is_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged_manifest = root / "input" / "manifest.json"
            output = root / "evidence"
            prepare_manifest(MANIFEST, staged_manifest)

            staged = json.loads(staged_manifest.read_text(encoding="utf-8"))
            self.assertEqual(
                staged["cases"][0]["external_reports"][0]["expected_sha256"],
                "0" * 64,
            )
            self.assertTrue(Path(staged["cases"][0]["request"]).is_absolute())
            self.assertTrue(
                Path(staged["cases"][0]["external_reports"][0]["source"])
                .is_absolute()
            )

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                run_review_evaluation(staged_manifest, output)
            summary = check_rejection(output, "failure")

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["cli_outcome"], "failure")
            self.assertTrue(
                (output / "review-rejection-exercise.json").is_file()
            )

    def test_successful_cli_outcome_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must be failure"):
                check_rejection(Path(directory), "success")


if __name__ == "__main__":
    unittest.main()
