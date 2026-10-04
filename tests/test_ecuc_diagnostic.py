from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.external_ecu import read_json, write_json
from automotive_workbench.project_ecuc import verify
from automotive_workbench.project_workflow import run_project
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticDependencyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source"
        shutil.copytree(ROOT / "examples/ecuc_diagnostic", self.source)
        self.path = self.source / "integration.project.json"
        self.project = read_json(self.path)
        shutil.copytree(self.source / "integration", self.source / "candidate")
        self.project["inputs"]["candidate"] = {
            k: [s.replace("integration/", "candidate/") for s in v]
            if isinstance(v, list)
            else v.replace("integration/", "candidate/")
            for k, v in self.project["inputs"]["candidate"].items()
        }

    def execute(self, name="run", config=None):
        write_json(self.path, self.project)
        result = run_project(
            self.path, self.root / name, config or BusConfig("socketcan", "p29-absent")
        )
        self.assertEqual(result["integrity_status"], "passed")
        path = Path(result["report_json"])
        for schema, data in [
            ("workbench-project", self.project),
            ("project-acceptance", read_json(path)),
            ("ecuc-project-acceptance", read_json(path.parent / "ecuc-stage.json")),
            ("ecuc-diagnostic-link", read_json(path.parent / "diagnostic-link.json")),
        ]:
            Draft202012Validator(
                read_json(ROOT / f"schemas/{schema}.schema.json")
            ).validate(data)
        external = path.parent / "external-ecu/external-ecu-report.json"
        if external.exists():
            Draft202012Validator(
                read_json(ROOT / "schemas/external-ecu-run.schema.json")
            ).validate(read_json(external))
        self.assertEqual(verify(path)["status"], "passed")
        return path

    def check(self, path):
        return read_json(path.parent / "ecuc-stage.json")["checks"][
            "diagnostic.read-version"
        ]

    def test_two_projects_portable_review_and_comparison(self):
        a, b = self.execute("a"), self.execute("b")
        self.assertEqual(read_json(a)["status"], "blocked")
        self.assertEqual(self.check(a)["reason"], "missing_build_files:executable")
        self.assertNotEqual(self.check(a)["run_id"], self.check(b)["run_id"])
        self.assertEqual(
            compare_project_reports(a, b, self.root / "comparison")["status"], "stable"
        )
        self.path = self.source / "transmitter.project.json"
        self.project = read_json(self.path)
        self.execute("tx")
        shutil.rmtree(self.source)
        self.assertEqual(
            run_project_review(a, self.root / "review")["status"], "answered"
        )
        self.assertEqual(
            validate_project_comparison(
                self.root / "comparison/project-comparison.json"
            )["status"],
            "passed",
        )
        (self.root / "a").rename(self.root / "moved")
        self.assertEqual(
            verify(self.root / "moved/bundle/project-report.json")["status"], "passed"
        )

    def test_static_rejection_never_launches_executor(self):
        p = self.source / "candidate/modules.arxml"
        p.write_text(p.read_text().replace("<VALUE>8</VALUE>", "<VALUE>12</VALUE>", 1))
        with patch(
            "automotive_workbench.ecuc_diagnostic.run_project_external"
        ) as runner:
            path = self.execute()
        runner.assert_not_called()
        self.assertEqual(read_json(path)["status"], "failed")
        self.assertEqual(self.check(path)["reason"], "static_acceptance_rejected")

    def test_unknown_semantics_identity_and_backend_do_not_execute(self):
        original = copy.deepcopy(self.project)
        for case, reason in [
            ("semantic", "configuration_semantic_provenance_missing"),
            ("identity", "diagnostic_identity_mismatch"),
            ("backend", "diagnostic_backend_mismatch"),
        ]:
            self.project = copy.deepcopy(original)
            config = None
            if case == "semantic":
                self.project["diagnostic"]["relation"] = "configuration-semantic"
            if case == "identity":
                self.project["diagnostic"]["identity"]["did"] += 1
            if case == "backend":
                config = BusConfig("virtual", "p29-absent")
            with patch(
                "automotive_workbench.ecuc_diagnostic.run_project_external"
            ) as runner:
                path = self.execute(case, config)
            runner.assert_not_called()
            self.assertEqual(self.check(path)["reason"], reason)
            self.assertFalse((path.parent / "external-ecu").exists())

    def test_historical_execution_replacement_even_rehashed_is_rejected(self):
        a, b = self.execute("a"), self.execute("b")
        shutil.rmtree(b.parent / "external-ecu")
        shutil.copytree(a.parent / "external-ecu", b.parent / "external-ecu")
        p = b.parent / "diagnostic-link.json"
        record = read_json(p)
        record["runtime_sha256"] = sha256_file(b.parent / record["runtime_path"])
        write_json(p, record)
        with self.assertRaisesRegex(ValueError, "context"):
            verify(b)

    def test_runtime_input_drift_after_rehash_is_rejected(self):
        path = self.execute()
        rawpath = path.parent / "external-ecu/external-ecu-report.json"
        raw = read_json(rawpath)
        p = rawpath.parent / "inputs/execution.json"
        spec = read_json(p)
        spec["startup_delay_s"] = 2
        write_json(p, spec)
        for item in raw["inventory"]:
            item["sha256"] = sha256_file(rawpath.parent / item["path"])
        write_json(rawpath, raw)
        linkpath = path.parent / "diagnostic-link.json"
        link = read_json(linkpath)
        link["runtime_sha256"] = sha256_file(rawpath)
        write_json(linkpath, link)
        with self.assertRaisesRegex(ValueError, "input drift"):
            verify(path)

    def test_missing_evidence_and_context_drift_rejected(self):
        path = self.execute()
        for case in ["missing", "context", "extra"]:
            dest = self.root / case
            shutil.copytree(path.parent, dest)
            if case == "missing":
                (dest / "external-ecu/external-ecu-report.json").unlink()
            if case == "extra":
                (dest / "inputs/unexpected.txt").write_text("unexpected")
            if case == "context":
                p = dest / "diagnostic-link.json"
                d = read_json(p)
                d["context"]["baseline_sha256"] = "a" * 64
                write_json(p, d)
            with self.subTest(case=case), self.assertRaises((ValueError, OSError)):
                verify(dest / "project-report.json")

    def test_invalid_declarations_reject_before_output(self):
        original = copy.deepcopy(self.project)
        for case in ["bool", "unknown-policy", "omitted", "extra", "duplicate"]:
            self.project = copy.deepcopy(original)
            d = self.project["diagnostic"]
            if case == "bool":
                d["identity"]["did"] = True
            if case == "unknown-policy":
                d["policy_ids"] = ["absent"]
            if case == "omitted":
                self.project["requirements"].pop()
            if case == "extra":
                d["inferred"] = True
            if case == "duplicate":
                d["policy_ids"] *= 2
            write_json(self.path, self.project)
            with self.subTest(case=case), self.assertRaises(ValueError):
                run_project(
                    self.path, self.root / case, BusConfig("socketcan", "p29-absent")
                )
            self.assertFalse((self.root / case).exists())

    def test_changed_diagnostic_identity_is_not_comparable(self):
        a = self.execute("a")
        self.project["diagnostic"]["identity"]["did"] += 1
        b = self.execute("b")
        self.assertEqual(
            compare_project_reports(a, b, self.root / "comparison")["status"],
            "not-comparable",
        )
