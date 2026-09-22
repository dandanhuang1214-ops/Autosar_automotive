from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from io import StringIO
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from automotive_workbench.can_io import BusConfig
from automotive_workbench.project_comparison import (
    _render_html,
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.project_workflow import run_project
from automotive_workbench.cli import main
from scripts.run_project_comparison_scenarios import run_comparison_scenarios


ROOT = Path(__file__).resolve().parents[1]


class ProjectComparisonTests(unittest.TestCase):
    def test_public_p18_scenario_is_portable(self) -> None:
        scenario = self.root / "scenario"
        result = run_comparison_scenarios(scenario)
        moved = self.root / "moved"
        shutil.copytree(scenario, moved)
        comparison = moved / "comparisons/scale-regression/project-comparison.json"

        validation = validate_project_comparison(comparison)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(validation["status"], "passed")
        class Links(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    for key, value in attrs:
                        if key == "href":
                            self.links.append(value)

        from urllib.parse import unquote

        for page in [moved / "index.html", *moved.glob("comparisons/*/index.html")]:
            parser = Links()
            parser.links = []
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertTrue(parser.links)
            for link in parser.links:
                self.assertTrue((page.parent / unquote(link)).is_file(), link)
        self.assertEqual(
            [item["status"] for item in result["comparisons"]],
            ["stable", "regressed", "regressed", "improved"],
        )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reports = {
            name: self._run_case(name)
            for name in ("baseline", "scale-change", "missing-init")
        }

    def _run_case(self, name: str) -> Path:
        source = self.root / "sources" / name
        shutil.copytree(ROOT / "examples/generate_arxml/bridge" / name, source)
        result = run_project(
            source / "project.json",
            self.root / "projects" / name,
            BusConfig("virtual", f"p18-{name}-{uuid.uuid4().hex}"),
        )
        return Path(result["report_json"])

    def _compare(self, baseline: str, candidate: str, name: str) -> dict:
        result = compare_project_reports(
            self.reports[baseline], self.reports[candidate], self.root / name
        )
        schema = json.loads(
            (ROOT / "schemas/project-comparison.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(result)
        return result

    def test_detects_scale_regression_and_dual_side_evidence(self) -> None:
        result = self._compare("baseline", "scale-change", "scale-regression")
        stages = {item["stage"]: item for item in result["stages"]}
        requirements = {item["id"]: item for item in result["requirements"]}

        self.assertEqual(result["status"], "regressed")
        self.assertEqual(stages["canonical"]["classification"], "regressed")
        self.assertEqual(stages["communication"]["classification"], "regressed")
        self.assertEqual(requirements["WIN-CFG-001"]["classification"], "regressed")
        self.assertEqual(
            {item["role"] for item in stages["canonical"]["evidence"]},
            {"baseline", "candidate"},
        )
        self.assertIn(
            "MAP-NUMERIC-MISMATCH",
            {item["finding"].get("code") for item in result["findings"]},
        )
        self.assertEqual(result["evidence_validation"]["status"], "passed")

    def test_detects_generation_regression_and_reverse_improvement(self) -> None:
        regression = self._compare("baseline", "missing-init", "generation-regression")
        improvement = self._compare("missing-init", "baseline", "improvement")

        self.assertEqual(regression["status"], "regressed")
        self.assertEqual(improvement["status"], "improved")
        self.assertIn(
            "CONTRACT-OPEN-ISSUE",
            {item["finding"].get("code") for item in regression["findings"]},
        )

    def test_identical_report_is_stable(self) -> None:
        result = self._compare("baseline", "baseline", "stable")

        self.assertEqual(result["status"], "stable")
        self.assertEqual(result["findings"], [])
        self.assertTrue(
            all(item["classification"] == "stable" for item in result["stages"])
        )
        self.assertTrue(
            all(
                item["classification"] == "stable"
                for item in result["requirements"]
            )
        )

    def test_html_escapes_report_content_and_keeps_evidence_visible(self) -> None:
        result = self._compare("baseline", "scale-change", "html")
        page = (self.root / "html/index.html").read_text(encoding="utf-8")
        self.assertIn("MAP-NUMERIC-MISMATCH", page)
        self.assertIn("skipped", page)
        self.assertIn("JSON Pointer:", page)
        self.assertIn("静态快照", page)
        result["findings"][0]["finding"]["message"] = '<script>alert("unsafe")</script>'
        result["baseline"]["source"] = 'javascript:alert(1)'
        page = _render_html(result)
        self.assertNotIn("<script>", page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn("&lt;script&gt;", page)

    def test_not_comparable_html_shows_reason_without_change_tables(self) -> None:
        self.reports["scale-change"].parent.joinpath("canonical.json").unlink()
        result = self._compare("baseline", "scale-change", "html-missing")
        page = (self.root / "html-missing/index.html").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "not-comparable")
        self.assertIn("candidate stage artifact is missing", page)
        self.assertNotIn("<table>", page)

    def test_requirement_set_mismatch_is_not_comparable(self) -> None:
        report_path = self.reports["scale-change"]
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        payload["requirements"].pop()
        report_path.write_text(json.dumps(payload), encoding="utf-8")

        result = self._compare("baseline", "scale-change", "not-comparable")

        self.assertEqual(result["status"], "not-comparable")
        self.assertIn("project requirement id set differs", result["basis"]["reasons"])
        self.assertEqual(result["stages"], [])

    def test_tamper_breaks_evidence_validation(self) -> None:
        output = self.root / "tamper"
        result = self._compare("baseline", "scale-change", "tamper")
        self.assertEqual(result["evidence_validation"]["status"], "passed")
        payload = json.loads(self.reports["scale-change"].read_text(encoding="utf-8"))
        payload["status"] = "passed"
        self.reports["scale-change"].write_text(json.dumps(payload), encoding="utf-8")

        validation = validate_project_comparison(output / "project-comparison.json")

        self.assertEqual(validation["status"], "failed")
        self.assertTrue(any("source hash changed" in item for item in validation["reasons"]))

    def test_tampered_stage_artifact_is_not_comparable(self) -> None:
        candidate_report = self.reports["scale-change"]
        payload = json.loads(candidate_report.read_text(encoding="utf-8"))
        stage_path = candidate_report.parent / payload["stages"]["canonical"]["path"]
        stage = json.loads(stage_path.read_text(encoding="utf-8"))
        stage["findings"] = []
        stage_path.write_text(json.dumps(stage), encoding="utf-8")

        result = self._compare("baseline", "scale-change", "stage-tamper")

        self.assertEqual(result["status"], "not-comparable")
        self.assertIn(
            "candidate stage artifact hash mismatch: canonical",
            result["basis"]["reasons"],
        )
        self.assertEqual(result["stages"], [])
        self.assertEqual(result["findings"], [])

    def test_same_status_reason_change_is_changed(self) -> None:
        candidate_root = self.root / "candidate-reason-change"
        shutil.copytree(self.reports["baseline"].parent, candidate_root)
        candidate_report = candidate_root / "project-report.json"
        payload = json.loads(candidate_report.read_text(encoding="utf-8"))
        payload["requirements"][0]["reason"] = "Equivalent status with revised rationale"
        candidate_report.write_text(json.dumps(payload), encoding="utf-8")

        result = compare_project_reports(
            self.reports["baseline"], candidate_report, self.root / "reason-change"
        )

        self.assertEqual(result["status"], "changed")
        self.assertEqual(result["requirements"][0]["classification"], "changed")
        with patch("sys.argv", [
            "workbench",
            "compare-projects",
            str(self.reports["baseline"]),
            str(candidate_report),
            "--output",
            str(self.root / "cli-reason-change"),
        ]), redirect_stdout(StringIO()):
            self.assertEqual(main(), 2)

    def test_rejects_nonempty_output_and_escaping_stage_path(self) -> None:
        output = self.root / "nonempty"
        output.mkdir()
        (output / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "empty or absent"):
            compare_project_reports(
                self.reports["baseline"], self.reports["scale-change"], output
            )

        payload = json.loads(
            self.reports["scale-change"].read_text(encoding="utf-8")
        )
        payload["stages"]["canonical"]["path"] = "../outside.json"
        self.reports["scale-change"].write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            compare_project_reports(
                self.reports["baseline"],
                self.reports["scale-change"],
                self.root / "escaping",
            )

    def test_rejects_modified_conclusions_counts_and_removed_evidence(self) -> None:
        import copy

        result = self._compare("baseline", "scale-change", "conclusion-tamper")
        path = self.root / "conclusion-tamper/project-comparison.json"
        mutations = (
            lambda value: value.update(status="stable"),
            lambda value: value["summary"].update(stage_change_count=999),
            lambda value: value["summary"].update(stage_change_count=True),
            lambda value: value["stages"][0].update(classification="improved"),
            lambda value: value["requirements"].clear(),
            lambda value: value["findings"].clear(),
            lambda value: value["stages"][0]["evidence"].clear(),
            lambda value: value.update(schema_version="unknown"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(result)
                mutate(changed)
                path.write_text(json.dumps(changed), encoding="utf-8")
                validation = validate_project_comparison(path)
                self.assertEqual(validation["status"], "failed")
                self.assertTrue(validation["reasons"])

    def test_rechecks_unchanged_stage_files_without_finding_references(self) -> None:
        self._compare("baseline", "baseline", "stable-stage-tamper")
        report = json.loads(self.reports["baseline"].read_text(encoding="utf-8"))
        stage = self.reports["baseline"].parent / report["stages"]["canonical"]["path"]
        stage.write_text("{}", encoding="utf-8")
        validation = validate_project_comparison(
            self.root / "stable-stage-tamper/project-comparison.json"
        )
        self.assertEqual(validation["status"], "failed")

    def test_verification_cli_is_read_only_and_accepts_authentic_regression(self) -> None:
        self._compare("baseline", "scale-change", "verify-cli")
        path = self.root / "verify-cli/project-comparison.json"
        original = path.read_bytes()
        with patch("sys.argv", ["workbench", "verify-project-comparison", str(path)]), redirect_stdout(StringIO()):
            self.assertEqual(main(), 0)
        self.assertEqual(path.read_bytes(), original)
        payload = json.loads(original)
        payload["status"] = "stable"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with patch("sys.argv", ["workbench", "verify-project-comparison", str(path)]), redirect_stdout(StringIO()):
            self.assertEqual(main(), 2)

    def test_malformed_comparisons_return_structured_failure(self) -> None:
        path = self.root / "malformed.json"
        for content in ("{", "[]", "null", "{}", '{"baseline": null}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(validate_project_comparison(path)["status"], "failed")
        self.assertEqual(
            validate_project_comparison(self.root / "missing.json")["status"], "failed"
        )

    def test_cli_returns_nonzero_for_regression_and_zero_for_stable(self) -> None:
        for candidate, name, expected_exit in (
            ("scale-change", "cli-regression", 2),
            ("baseline", "cli-stable", 0),
        ):
            with self.subTest(candidate=candidate):
                with patch("sys.argv", [
                    "workbench",
                    "compare-projects",
                    str(self.reports["baseline"]),
                    str(self.reports[candidate]),
                    "--output",
                    str(self.root / name),
                ]), redirect_stdout(StringIO()):
                    self.assertEqual(main(), expected_exit)


if __name__ == "__main__":
    unittest.main()
