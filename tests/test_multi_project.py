from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.evidence_bundle import verify_evidence_bundle
from automotive_workbench.project_workflow import load_project, run_project
from automotive_workbench.project_declared import bind_declared_paths
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.review import validate_citations

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class MultiProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        shutil.copytree(ROOT / "examples/thermal_control", self.source)
        self.project = self.source / "project.json"

    def schema(self, name, value):
        Draft202012Validator(
            read(ROOT / "schemas" / (name + ".schema.json")),
            format_checker=FormatChecker(),
        ).validate(value)

    def run_case(self, name="run"):
        output = self.root / name
        result = run_project(self.project, output, default_communication_config())
        report_path = Path(result["report_json"])
        report = read(report_path)
        self.schema("project-acceptance", report)
        self.assertEqual(result["integrity_status"], "passed")
        if report["stages"]["communication"]["path"]:
            self.schema(
                "declared-communication-binding",
                read(report_path.parent / report["stages"]["communication"]["path"]),
            )
        return report_path, report

    def test_thermal_project_runs_and_binds_all_five_paths(self):
        project, snapshots = load_project(self.project)
        self.schema("workbench-project", project)
        self.assertEqual(
            snapshots["vectors.json"],
            (self.source / "communication_vectors.json").read_bytes(),
        )
        path, report = self.run_case()
        self.assertEqual(report["status"], "passed")
        communication = read(path.parent / report["stages"]["communication"]["path"])
        self.assertEqual(
            (communication["path_count"], communication["bound_count"]), (5, 5)
        )
        self.assertEqual(
            communication["bindings"]["cooling-request"]["Enable"]["path"]["direction"],
            "rx",
        )
        self.assertEqual(
            communication["bindings"]["thermal-status"]["CoolantTemperature"][
                "raw_value"
            ],
            1223,
        )
        self.assertTrue(
            all(
                x["evidence"]["pointer"].startswith("/") for x in report["requirements"]
            )
        )

    def test_window_old_and_declared_projects_remain_usable(self):
        for project_file, version in [
            ("project.json", "project-acceptance-0.1"),
            ("project-declared.json", "project-acceptance-0.3"),
        ]:
            result = run_project(
                ROOT / "examples/window_control" / project_file,
                self.root / project_file,
                default_communication_config(),
            )
            report = read(Path(result["report_json"]))
            self.assertEqual(report["schema_version"], version)
            self.assertEqual(report["status"], "passed")

    def test_generation_bridge_can_use_declared_project_version(self):
        source = self.root / "generated"
        shutil.copytree(ROOT / "examples/generate_arxml/bridge/baseline", source)
        shutil.copyfile(
            ROOT / "examples/window_control/communication_vectors.json",
            source / "vectors.json",
        )
        project = read(source / "project.json")
        project["schema_version"] = "workbench-project-0.3"
        project["comparison_key"] = "generated-window-v1"
        project["inputs"]["vectors"] = "vectors.json"
        for requirement in project["requirements"]:
            if (
                requirement["stage"] == "communication"
                and requirement["pointer"] == "/runtime_status"
            ):
                requirement["pointer"] = "/status"
        write(source / "project.json", project)
        self.schema("workbench-project", project)
        result = run_project(
            source / "project.json",
            self.root / "generated-result",
            default_communication_config(),
        )
        report = read(Path(result["report_json"]))
        self.schema("project-acceptance", report)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["stages"]["generation"]["status"], "passed")
        self.assertEqual(
            run_project_review(
                Path(result["report_json"]), self.root / "generated-review"
            )["status"],
            "answered",
        )

    def test_invalid_declaration_or_missing_path_never_opens_or_writes(self):
        original = read(self.source / "communication_vectors.json")
        for mutation in ["unknown", "coverage", "duplicate_key"]:
            value = copy.deepcopy(original)
            if mutation == "unknown":
                value["vectors"][-1]["signals"]["Unknown"] = 1
            elif mutation == "coverage":
                value["vectors"].pop()
            if mutation == "duplicate_key":
                (self.source / "communication_vectors.json").write_text(
                    '{"vectors":[],"vectors":[]}', encoding="utf-8"
                )
            else:
                write(self.source / "communication_vectors.json", value)
            output = self.root / mutation
            with (
                self.subTest(mutation=mutation),
                patch(
                    "automotive_workbench.declared_communication.probe_can_backend"
                ) as probe,
                self.assertRaises(ValueError),
            ):
                run_project(self.project, output, default_communication_config())
            probe.assert_not_called()
            self.assertFalse(output.exists())

    def test_static_regression_skips_runtime_and_reviews_findings(self):
        baseline, _ = self.run_case("baseline")
        contract = self.source / "canonical_contract.json"
        value = read(contract)
        value["signals"][0]["resolution"] = "2"
        write(contract, value)
        with patch(
            "automotive_workbench.project_workflow.run_bound_communication"
        ) as runtime:
            candidate, report = self.run_case("candidate")
        runtime.assert_not_called()
        self.assertEqual(
            report["stages"]["communication"], {"status": "skipped", "path": None}
        )
        review = run_project_review(candidate, self.root / "review")
        self.assertEqual(review["status"], "answered")
        self.assertIn("MAP-NUMERIC-MISMATCH", json.dumps(review))
        comparison = compare_project_reports(
            baseline, candidate, self.root / "comparison"
        )
        self.schema("project-comparison", comparison)
        self.assertEqual(comparison["schema_version"], "project-comparison-0.2")
        self.assertEqual(comparison["status"], "regressed")
        self.assertEqual(comparison["evidence_validation"]["status"], "passed")

    def test_compatible_ids_do_not_hide_different_requirement_definitions(self):
        baseline, _ = self.run_case("baseline")
        original = read(self.project)
        for field, new in [
            ("expected", True),
            ("text", "A different acceptance task"),
            ("pointer", "/path_count"),
        ]:
            project = copy.deepcopy(original)
            project["requirements"][-1][field] = new
            write(self.project, project)
            candidate, _ = self.run_case(field)
            comparison = compare_project_reports(
                baseline, candidate, self.root / (field + "-comparison")
            )
            self.assertEqual(comparison["status"], "not-comparable")
            self.assertTrue(
                any("definition differs" in x for x in comparison["basis"]["reasons"])
            )
        project = copy.deepcopy(original)
        project["comparison_key"] = "another-project"
        write(self.project, project)
        candidate, _ = self.run_case("other")
        self.assertEqual(
            compare_project_reports(
                baseline, candidate, self.root / "other-comparison"
            )["status"],
            "not-comparable",
        )

    def test_changed_vector_definition_is_not_comparable(self):
        baseline, _ = self.run_case("baseline")
        path = self.source / "communication_vectors.json"
        value = read(path)
        value["vectors"][0]["signals"]["FanDuty"] = 50
        write(path, value)
        candidate, _ = self.run_case("candidate")
        self.assertEqual(
            compare_project_reports(baseline, candidate, self.root / "comparison")[
                "status"
            ],
            "not-comparable",
        )

    def test_relocation_revalidates_bundle_review_and_comparison(self):
        report, _ = self.run_case("original")
        review = run_project_review(report, self.root / "original/review")
        comparison = compare_project_reports(
            report, report, self.root / "original/comparison"
        )
        self.assertEqual(comparison["status"], "stable")
        (self.root / "original").rename(self.root / "moved")
        shutil.rmtree(self.source)
        moved = self.root / "moved"
        self.assertEqual(
            verify_evidence_bundle(
                moved / "bundle",
                moved / "manifest.json",
                self.root / "verification",
                base=moved,
            )["status"],
            "passed",
        )
        self.assertEqual(
            validate_citations(moved / "review/review-request.json", review)["status"],
            "passed",
        )
        self.assertEqual(
            validate_project_comparison(moved / "comparison/project-comparison.json")[
                "status"
            ],
            "passed",
        )
        self.assertEqual(
            run_project_review(
                moved / "bundle/project-report.json", self.root / "rereview"
            )["status"],
            "answered",
        )

    def test_runtime_and_input_tampering_invalidates_consumers(self):
        report, _ = self.run_case()
        target = report.parent / "communication/runtime/declared-runtime-report.json"
        original = target.read_bytes()
        target.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "modified"):
            run_project_review(report, self.root / "review")
        comparison = compare_project_reports(report, report, self.root / "comparison")
        self.assertEqual(comparison["status"], "not-comparable")
        self.assertTrue(any("provenance" in r for r in comparison["basis"]["reasons"]))
        target.write_bytes(original)
        value = read(report)
        value["comparison_basis"]["key"] = "tampered"
        write(report, value)
        with self.assertRaisesRegex(ValueError, "basis disagrees"):
            run_project_review(report, self.root / "changed-review")

    def test_binding_rejects_runtime_identity_and_observation_drift(self):
        path, _ = self.run_case()
        mapping = read(path.parent / "mapping.json")
        original = read(
            path.parent / "communication/runtime/declared-runtime-report.json"
        )
        for field, new in [("message", "Wrong"), ("direction", "rx"), ("id", "wrong")]:
            runtime = copy.deepcopy(original)
            runtime["vectors"]["thermal-status"][field] = new
            self.assertEqual(bind_declared_paths(mapping, runtime)["status"], "failed")
        runtime = copy.deepcopy(original)
        runtime["vectors"]["thermal-status"]["observed"]["frame_id"] += 1
        self.assertEqual(bind_declared_paths(mapping, runtime)["status"], "failed")
        runtime = copy.deepcopy(original)
        runtime["plan"]["vectors"].pop()
        self.assertTrue(
            any(
                x["code"] == "DECLARED-PATH-MISSING"
                for x in bind_declared_paths(mapping, runtime)["findings"]
            )
        )

    def test_schema_loader_parity_for_project_version_fields(self):
        original = read(self.project)
        validator = Draft202012Validator(
            read(ROOT / "schemas/workbench-project.schema.json")
        )
        for mutation in ["no_vectors", "no_key", "legacy_vectors", "bad_key", "extra"]:
            value = copy.deepcopy(original)
            if mutation == "no_vectors":
                del value["inputs"]["vectors"]
            elif mutation == "no_key":
                del value["comparison_key"]
            elif mutation == "legacy_vectors":
                value["schema_version"] = "workbench-project-0.1"
                del value["comparison_key"]
            elif mutation == "bad_key":
                value["comparison_key"] = "bad/key"
            elif mutation == "extra":
                value["extra"] = True
            write(self.project, value)
            with self.subTest(mutation=mutation):
                self.assertFalse(validator.is_valid(value))
                with self.assertRaises(ValueError):
                    load_project(self.project)


if __name__ == "__main__":
    unittest.main()
