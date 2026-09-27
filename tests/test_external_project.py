from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.external_ecu import read_json, write_json
from automotive_workbench.project_workflow import load_project, run_project
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import compare_project_reports
from automotive_workbench.project_declared import validate_declared_sources
from scripts.run_external_project_scenarios import prepare

ROOT = Path(__file__).resolve().parents[1]


class ExternalProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.project, self.spec, self.profile = prepare(self.source, None)
        self.path = self.source / "project.json"
        self.save()
        schemas = [read_json(p) for p in (ROOT / "schemas").glob("*.json")]
        self.registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in schemas
        )

    def save(self):
        write_json(self.path, self.project)
        write_json(self.source / "execution.json", self.spec)
        write_json(self.source / "profile.json", self.profile)

    def schema(self, name, value):
        Draft202012Validator(
            read_json(ROOT / "schemas" / (name + ".schema.json")),
            registry=self.registry,
        ).validate(value)

    def execute(self, name="run"):
        result = run_project(
            self.path, self.root / name, BusConfig("socketcan", self.spec["channel"])
        )
        self.assertEqual(result["integrity_status"], "passed")
        path = Path(result["report_json"])
        self.schema("project-acceptance", read_json(path))
        validate_declared_sources(path, read_json(path))
        return path

    def test_blocked_project_schema_review_compare_and_relocation(self):
        self.schema("workbench-project", self.project)
        path = self.execute()
        report = read_json(path)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["stages"]["external_ecu"]["status"], "blocked")
        self.schema(
            "external-ecu-project-stage", read_json(path.parent / "external-ecu.json")
        )
        self.assertEqual(
            run_project_review(path, self.root / "review")["status"], "answered"
        )
        self.assertEqual(
            compare_project_reports(path, path, self.root / "compare")["status"],
            "stable",
        )
        shutil.rmtree(self.source)
        path.parent.parent.rename(self.root / "moved")
        moved = self.root / "moved/bundle/project-report.json"
        self.assertEqual(
            run_project_review(moved, self.root / "moved-review")["status"], "answered"
        )

    def test_static_failure_skips_communication_and_ecu(self):
        contract = self.source / self.project["inputs"]["contract"]
        data = read_json(contract)
        data["signals"][0]["resolution"] = "2"
        write_json(contract, data)
        with (
            patch(
                "automotive_workbench.project_workflow.run_project_external"
            ) as external,
            patch(
                "automotive_workbench.project_workflow.run_bound_communication"
            ) as communication,
        ):
            path = self.execute()
        external.assert_not_called()
        communication.assert_not_called()
        self.assertEqual(read_json(path)["status"], "failed")
        self.assertEqual(
            read_json(path)["stages"]["external_ecu"],
            {"status": "skipped", "path": None},
        )
        self.assertEqual(
            run_project_review(path, self.root / "review")["status"], "answered"
        )

    def test_generation_bridge_remains_bound_in_v05(self):
        baseline = ROOT / "examples/generate_arxml/bridge/baseline"
        generated = read_json(baseline / "project.json")
        for key in ("dbc", "contract", "intent"):
            shutil.copyfile(
                baseline / generated["inputs"][key],
                self.source / generated["inputs"][key],
            )
            self.project["inputs"][key] = generated["inputs"][key]
        self.project["generation"] = generated["generation"]
        for key in ("source_docx", "issue_report"):
            source = baseline / generated["generation"][key]
            target = self.source / source.name
            shutil.copyfile(source, target)
            self.project["generation"][key] = source.name
        self.save()
        self.schema("workbench-project", self.project)
        path = self.execute()
        self.assertEqual(read_json(path)["stages"]["generation"]["status"], "passed")
        shutil.rmtree(self.source)
        path.parent.parent.rename(self.root / "moved")
        self.assertEqual(
            run_project_review(
                self.root / "moved/bundle/project-report.json", self.root / "review"
            )["status"],
            "answered",
        )

    def test_external_boolean_tamper_cannot_equal_integer(self):
        path = self.execute()
        stage_path = path.parent / "external-ecu.json"
        stage = read_json(stage_path)
        stage["launch_ecu"] = 1
        write_json(stage_path, stage)
        report = read_json(path)
        for source in report["source_artifacts"]:
            if source["source"] == "bundle/external-ecu.json":
                source["sha256"] = sha256_file(stage_path)
        write_json(path, report)
        with self.assertRaises(ValueError):
            run_project_review(path, self.root / "review")

    def test_backend_and_binding_drift_reject_before_output(self):
        for config in (
            BusConfig("virtual", self.spec["channel"]),
            BusConfig("socketcan", "other"),
            BusConfig("socketcan", self.spec["channel"], fd=True),
        ):
            with (
                self.subTest(config=config),
                self.assertRaises(ValueError),
                patch("subprocess.Popen") as spawn,
            ):
                run_project(self.path, self.root / "out", config)
            spawn.assert_not_called()
            self.assertFalse((self.root / "out").exists())
        self.profile["response_id"] += 1
        self.save()
        with self.assertRaises(ValueError):
            load_project(self.path)

    def test_v05_loader_schema_and_legacy_version_parity(self):
        original = copy.deepcopy(self.project)
        for mutate in (
            lambda p: p["inputs"].pop("execution"),
            lambda p: p.update(schema_version="workbench-project-0.4"),
            lambda p: p.update(schema_version=[]),
            lambda p: p["requirements"][-1].update(stage="unknown"),
        ):
            candidate = copy.deepcopy(original)
            mutate(candidate)
            write_json(self.path, candidate)
            self.assertFalse(
                Draft202012Validator(
                    read_json(ROOT / "schemas/workbench-project.schema.json"),
                    registry=self.registry,
                ).is_valid(candidate)
            )
            with self.assertRaises(ValueError):
                load_project(self.path)

    def test_rehashed_stage_and_acceptance_tamper_refused(self):
        path = self.execute()
        original = path.read_bytes()
        stage_path = path.parent / "external-ecu.json"
        stage = read_json(stage_path)
        stage["reason"] = "invented reason"
        write_json(stage_path, stage)
        report = read_json(path)
        for source in report["source_artifacts"]:
            if source["source"] == "bundle/external-ecu.json":
                source["sha256"] = sha256_file(stage_path)
        write_json(path, report)
        with self.assertRaisesRegex(ValueError, "External stage disagrees"):
            run_project_review(path, self.root / "rejected")
        self.assertFalse((self.root / "rejected").exists())
        # Regenerate a valid independent result, then alter project outcome only.
        path = self.execute("another")
        report = read_json(path)
        report["status"] = "passed"
        write_json(path, report)
        with self.assertRaises(ValueError):
            run_project_review(path, self.root / "rejected-outcome")
        self.assertTrue(original)

    def test_changed_definition_and_execution_are_not_comparable(self):
        baseline = self.execute("baseline")
        self.project["requirements"][-1]["expected"] = "00"
        self.save()
        changed = self.execute("definition")
        self.assertEqual(
            compare_project_reports(
                baseline, changed, self.root / "compare-definition"
            )["status"],
            "not-comparable",
        )
        self.project["requirements"][-1]["expected"] = self.profile["expected_data_hex"]
        self.spec["launch_ecu"] = False
        self.save()
        changed = self.execute("execution")
        self.assertEqual(
            compare_project_reports(baseline, changed, self.root / "compare-execution")[
                "status"
            ],
            "not-comparable",
        )

    def test_snapshot_used_after_original_profile_changes(self):
        from automotive_workbench.project_external import run_project_external

        original = copy.deepcopy(self.profile)

        def run_from_saved(inputs, bundle):
            write_json(self.source / "profile.json", {**original, "response_id": 241})
            return run_project_external(inputs, bundle)

        with patch(
            "automotive_workbench.project_workflow.run_project_external",
            side_effect=run_from_saved,
        ):
            path = self.execute()
        saved = read_json(path.parent / "external-ecu/inputs/profile.json")
        self.assertEqual(saved, original)


if __name__ == "__main__":
    unittest.main()
