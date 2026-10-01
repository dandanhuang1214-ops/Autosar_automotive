from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from automotive_workbench.can_io import BusConfig
from automotive_workbench.project_ecuc import declaration, verify
from automotive_workbench.project_workflow import load_project, run_project
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class EcucProjectAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "inputs"
        shutil.copytree(ROOT / "examples/ecuc_acceptance", self.source)
        self.path = self.source / "integration.project.json"
        self.project = read(self.path)
        shutil.copytree(self.source / "integration", self.source / "candidate")
        self.project["inputs"]["candidate"] = {
            k: (
                [x.replace("integration/", "candidate/") for x in v]
                if isinstance(v, list)
                else v.replace("integration/", "candidate/")
            )
            for k, v in self.project["inputs"]["candidate"].items()
        }
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.project), encoding="utf-8")

    def mutate(self, old, new, file="modules.arxml"):
        p = self.source / "candidate" / file
        data = p.read_text(encoding="utf-8")
        self.assertIn(old, data)
        p.write_text(data.replace(old, new, 1), encoding="utf-8")

    def execute(self, name="run"):
        self.save()
        with patch(
            "automotive_workbench.project_workflow.run_bound_communication"
        ) as bus:
            result = run_project(
                self.path, self.root / name, BusConfig("virtual", "unused")
            )
        bus.assert_not_called()
        self.assertEqual(result["integrity_status"], "passed")
        path = Path(result["report_json"])
        for schema, value in [
            ("workbench-project", self.project),
            ("project-acceptance", read(path)),
            ("ecuc-project-acceptance", read(path.parent / "ecuc-stage.json")),
        ]:
            Draft202012Validator(
                read(ROOT / "schemas" / (schema + ".schema.json"))
            ).validate(value)
        self.assertEqual(verify(path)["status"], "passed")
        return path

    def test_two_structurally_distinct_projects_same_engine_and_no_bus(self):
        p = self.execute()
        self.assertEqual(read(p)["status"], "passed")
        self.path = self.source / "transmitter.project.json"
        self.project = read(self.path)
        q = self.execute("transmitter")
        stage = read(q.parent / "ecuc-stage.json")
        self.assertEqual(stage["status"], "passed")
        self.assertEqual(stage["checks"]["application"]["status"], "unassessed")
        self.assertEqual(
            read(q.parent / "ecuc/after/ecuc-review.json")["summary"][
                "communication_paths"
            ],
            1,
        )

    def test_task_gap_fails_declared_acceptance_and_has_impact_witnesses(self):
        self.mutate("/Demo/Os/TaskA</VALUE-REF>", "</VALUE-REF>")
        path = self.execute()
        report = read(path)
        self.assertEqual(report["status"], "failed")
        check = read(path.parent / "ecuc-stage.json")["checks"]["task_bindings"]
        self.assertEqual(check["reason"], "structural_gap")
        self.assertTrue(check["affected_objects"])
        self.assertEqual(
            run_project_review(path, self.root / "review")["status"], "answered"
        )

    def test_communication_regression_compares_and_replays(self):
        a = self.execute("baseline")
        self.mutate("/Demo/EcuC/C</VALUE-REF>", "/Demo/EcuC/Missing</VALUE-REF>")
        b = self.execute("candidate")
        comparison = compare_project_reports(a, b, self.root / "comparison")
        self.assertEqual(comparison["status"], "regressed")
        self.assertEqual(comparison["schema_version"], "project-comparison-0.3")
        Draft202012Validator(
            read(ROOT / "schemas/project-comparison.schema.json")
        ).validate(comparison)
        self.assertEqual(
            validate_project_comparison(
                self.root / "comparison/project-comparison.json"
            )["status"],
            "passed",
        )

    def test_missing_coverage_and_vendor_change_remain_unassessed(self):
        self.project["inputs"]["candidate"]["applications"] = []
        self.project["requirements"] = [
            x for x in self.project["requirements"] if x["id"] == "APPLICATION"
        ]
        path = self.execute("missing")
        self.assertEqual(read(path)["status"], "unassessed")
        self.assertEqual(
            run_project_review(path, self.root / "review")["status"], "answered"
        )
        self.project["requirements"][0].update(
            id="IMPACT", pointer="/checks/impact/status"
        )
        self.mutate(
            "<SHORT-NAME>ValueA</SHORT-NAME>",
            "<SHORT-NAME>ValueA</SHORT-NAME><VENDOR>opaque</VENDOR>",
        )
        path = self.execute("opaque")
        self.assertEqual(read(path)["status"], "unassessed")

    def test_duplicate_identity_blocks_impact(self):
        self.project["requirements"] = [
            x for x in self.project["requirements"] if x["id"] == "IMPACT"
        ]
        self.mutate("<SHORT-NAME>TaskB</SHORT-NAME>", "<SHORT-NAME>TaskA</SHORT-NAME>")
        path = self.execute()
        self.assertEqual(read(path)["status"], "blocked")

    def test_historical_log_does_not_change_current_acceptance(self):
        self.mutate(
            "Historical task binding failure",
            "More historical ERROR observations",
            "tool.log",
        )
        path = self.execute()
        self.assertEqual(read(path)["status"], "passed")
        self.assertTrue(
            read(path.parent / "ecuc/ecuc-impact.json")["historical_logs_changed"]
        )

    def test_project_replays_after_originals_removed_and_bundle_moved(self):
        path = self.execute()
        shutil.rmtree(self.source)
        path.parent.parent.rename(self.root / "relocated")
        moved = self.root / "relocated/bundle/project-report.json"
        self.assertEqual(verify(moved)["status"], "passed")
        self.assertEqual(
            run_project_review(moved, self.root / "review")["status"], "answered"
        )

    def test_rejects_forged_report_stage_html_source_and_inventory(self):
        path = self.execute()
        for name in ["report", "stage", "html", "source", "inventory"]:
            with self.subTest(name=name):
                dest = self.root / name
                shutil.copytree(path.parent, dest)
                if name in {"report", "stage"}:
                    p = dest / (
                        "project-report.json" if name == "report" else "ecuc-stage.json"
                    )
                    data = read(p)
                    data["status"] = "failed"
                    p.write_text(json.dumps(data))
                elif name == "html":
                    (dest / "index.html").write_text("forged")
                elif name == "source":
                    p = dest / "ecuc/after/snapshot/project/modules.arxml"
                    p.write_bytes(
                        p.read_bytes().replace(
                            b"<VALUE>8</VALUE>", b"<VALUE>12</VALUE>"
                        )
                    )
                else:
                    (dest / "extra.txt").write_text("extra")
                with self.assertRaises(ValueError):
                    verify(dest / "project-report.json")
                with self.assertRaises(ValueError):
                    run_project_review(
                        dest / "project-report.json", self.root / ("review-" + name)
                    )

    def test_policy_and_baseline_drift_are_not_comparable(self):
        a = self.execute("before")
        self.project["requirements"][0]["text"] = "Different policy"
        b = self.execute("policy")
        self.assertEqual(
            compare_project_reports(a, b, self.root / "c1")["status"], "not-comparable"
        )
        self.project["requirements"][0]["text"] = read(a)["requirements"][0]["text"]
        self.project["inputs"]["baseline"] = copy.deepcopy(
            self.project["inputs"]["candidate"]
        )
        self.mutate("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        c = self.execute("changed-baseline")
        self.assertEqual(
            compare_project_reports(a, c, self.root / "c2")["status"], "not-comparable"
        )

    def test_invalid_declarations_rejected_before_output(self):
        for kind in ["extra", "pointer", "duplicate", "expectation", "empty", "paths"]:
            project = copy.deepcopy(self.project)
            if kind == "extra":
                project["auto_generate"] = True
            if kind == "pointer":
                project["requirements"][0]["pointer"] = "/historical_tool_logs"
            if kind == "duplicate":
                project["requirements"].append(project["requirements"][0])
            if kind == "expectation":
                project["requirements"][0]["expected"] = "unassessed"
            if kind == "empty":
                project["requirements"] = []
            if kind == "paths":
                project["inputs"]["candidate"]["applications"] = [False]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                declaration(project)
        self.project["requirements"][0]["pointer"] = []
        self.save()
        with self.assertRaises(ValueError):
            run_project(
                self.path, self.root / "invalid", BusConfig("virtual", "unused")
            )
        self.assertFalse((self.root / "invalid").exists())

    def test_frozen_capture_does_not_reopen_originals(self):
        from automotive_workbench.project_ecuc import run

        project, snapshots = load_project(self.path)
        shutil.rmtree(self.source)
        result = run(project, snapshots, self.root / "frozen")
        self.assertEqual(result["status"], "passed")

    def test_html_escapes_declared_text(self):
        self.project["name"] = "<script>attack</script>"
        self.project["requirements"][0]["text"] = "<img src=x onerror=attack>"
        path = self.execute()
        html = (path.parent / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_missing_application_never_becomes_current_task_failure(self):
        self.project["inputs"]["candidate"]["applications"] = []
        path = self.execute()
        self.assertEqual(read(path)["status"], "unassessed")
        stage = read(path.parent / "ecuc-stage.json")
        self.assertEqual(stage["checks"]["task_bindings"]["status"], "unassessed")

    def test_unknown_stage_status_not_accepted_under_old_contract(self):
        from automotive_workbench.project_review import load_project_report

        p = self.root / "old.json"
        p.write_text(
            json.dumps(
                {
                    "artifact_type": "project-acceptance",
                    "schema_version": "project-acceptance-0.5",
                    "status": "unassessed",
                    "name": "old",
                    "stages": {},
                }
            )
        )
        with self.assertRaises(ValueError):
            load_project_report(p)

    def test_rehashed_forged_stage_cannot_hide_task_failure(self):
        from automotive_workbench.ecuc_project import sha

        self.mutate("/Demo/Os/TaskA</VALUE-REF>", "</VALUE-REF>")
        path = self.execute()
        stage_path = path.parent / "ecuc-stage.json"
        stage = read(stage_path)
        stage["status"] = "passed"
        stage["checks"]["task_bindings"]["status"] = "passed"
        stage_path.write_text(json.dumps(stage), encoding="utf-8")
        report = read(path)
        report["status"] = "passed"
        report["stages"]["ecuc"]["status"] = "passed"
        for row in report["requirements"]:
            row.update(status="passed", actual="passed")
            row["evidence"]["sha256"] = sha(stage_path.read_bytes())
        for row in report["source_artifacts"]:
            if row["source"] == "bundle/ecuc-stage.json":
                row["sha256"] = sha(stage_path.read_bytes())
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stage differs from replay"):
            verify(path)
