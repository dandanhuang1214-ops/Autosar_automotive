from __future__ import annotations

import hashlib
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
    def test_existing_gold_fixtures_are_sha256_pinned(self) -> None:
        manifest = load_evaluation_manifest(MANIFEST)
        pinned_sources = 0
        for case in manifest["cases"]:
            request_path = MANIFEST.parent / case["request"]
            request = json.loads(request_path.read_text(encoding="utf-8"))
            for artifact in request["artifact_registry"]:
                source = request_path.parent / artifact["source"]
                if not source.is_file():
                    continue
                pinned_sources += 1
                self.assertEqual(
                    artifact.get("expected_sha256"),
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    f"unpinned or stale evaluation source: {source}",
                )
        self.assertEqual(pinned_sources, 17)

    def test_gold_evaluation_meets_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(MANIFEST, output)
            persisted = json.loads(
                (output / "review-evaluation.json").read_text(encoding="utf-8")
            )
            markdown = (output / "review-evaluation.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["case_count"], 14)
        self.assertEqual(result["check_count"], 30)
        self.assertEqual(result["repeat_runs"], 3)
        self.assertEqual(
            result["domain_check_counts"],
            {"can": 5, "core": 11, "dbc": 5, "dtc": 4, "uds": 5},
        )
        self.assertTrue(
            all(value == 1.0 for value in result["domain_check_accuracy"].values())
        )
        self.assertTrue(all(case["passed"] for case in result["cases"]))
        self.assertEqual(result["metrics"]["false_conflict_count"], 0)
        self.assertTrue(
            all(
                value == 1.0
                for key, value in result["metrics"].items()
                if key != "false_conflict_count"
            )
        )
        self.assertEqual(persisted["schema_version"], "review-evaluation-result-0.2")
        self.assertIn("does not use an LLM judge", markdown)

    def test_rejects_duplicate_evaluation_case(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"].append(manifest["cases"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate.*case_id"):
                load_evaluation_manifest(path)

    def test_v01_manifest_defaults_cases_to_core_domain(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["schema_version"] = "review-evaluation-0.1"
        for case in manifest["cases"]:
            case.pop("domain")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            loaded = load_evaluation_manifest(path)

        self.assertTrue(all(case["domain"] == "core" for case in loaded["cases"]))


if __name__ == "__main__":
    unittest.main()
