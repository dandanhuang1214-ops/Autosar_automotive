from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_workflow import run_project
from automotive_workbench.review import validate_citations
from scripts.run_project_review_scenarios import run_scenarios


ROOT = Path(__file__).resolve().parents[1]


class ProjectReviewTests(unittest.TestCase):
    def test_public_p17_scenario_covers_normal_failures_and_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "p17"
            result = run_scenarios(source)
            moved = root / "moved"
            shutil.copytree(source, moved)
            request = moved / "reviews/scale-change/review-request.json"
            review = json.loads(
                (moved / "reviews/scale-change/review-result.json").read_text(
                    encoding="utf-8"
                )
            )
            relocated_validation = validate_citations(request, review)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            [item["project_status"] for item in result["cases"]],
            ["passed", "failed", "failed"],
        )
        self.assertTrue(
            all(item["citation_validation"] == "passed" for item in result["cases"])
        )
        self.assertEqual(result["unsupported_claim"]["status"], "refused")
        self.assertEqual(relocated_validation["status"], "passed")

    def _run_case(self, case_name: str, root: Path) -> Path:
        source = root / case_name / "source"
        shutil.copytree(ROOT / "examples/generate_arxml/bridge" / case_name, source)
        result = run_project(
            source / "project.json",
            root / case_name / "acceptance",
            BusConfig("virtual", f"p17-{case_name}-{uuid.uuid4().hex}"),
        )
        return Path(result["report_json"])

    def test_reviews_actual_scale_failure_with_exact_citations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("scale-change", root)
            result = run_project_review(report, root / "review")
            markdown = (root / "review/project-review.md").read_text(
                encoding="utf-8"
            )

        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citation_validation"]["status"], "passed")
        self.assertIn("MAP-NUMERIC-MISMATCH", markdown)
        self.assertIn("communication stage status is skipped", markdown)
        self.assertTrue(all(item["status"] == "supported" for item in result["checks"]))

    def test_reviews_actual_generation_failure_and_preserves_upstream_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("missing-init", root)
            result = run_project_review(report, root / "review")
            contents = {item["content"] for item in result["citations"]}

        self.assertEqual(result["status"], "answered")
        self.assertIn("CONTRACT-OPEN-ISSUE", contents)
        self.assertIn("CORE-030-CONNECTOR-UNCONNECTED", contents)
        self.assertIn("skipped", contents)

    def test_refuses_physical_ecu_claim_absent_from_project_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("scale-change", root)
            result = run_project_review(
                report,
                root / "review",
                "Physical ECU flash timing was measured and certified.",
            )

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["checks"][0]["status"], "unsupported")
        self.assertEqual(result["refusal_reasons"][0]["code"], "REVIEW-NO-EVIDENCE")

    def test_accepts_an_existing_empty_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("scale-change", root)
            output = root / "review"
            output.mkdir()
            result = run_project_review(report, output)

        self.assertEqual(result["status"], "answered")

    def test_missing_stage_artifact_refuses_instead_of_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("scale-change", root)
            canonical = report.parent / "canonical.json"
            canonical.unlink()
            result = run_project_review(report, root / "review")

        self.assertEqual(result["status"], "refused")
        self.assertIn(
            "REVIEW-ARTIFACT-MISSING",
            {item["code"] for item in result["refusal_reasons"]},
        )

    def test_rejects_nonempty_output_and_escaping_stage_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._run_case("scale-change", root)
            output = root / "review"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_project_review(report, output)
            self.assertEqual((output / "keep.txt").read_text(), "keep")

            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["stages"]["canonical"]["path"] = "../outside.json"
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes"):
                run_project_review(report, root / "fresh")


if __name__ == "__main__":
    unittest.main()
