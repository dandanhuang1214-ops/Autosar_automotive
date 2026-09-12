from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.can_io import BusConfig
from automotive_workbench.evidence_bundle import verify_evidence_bundle
from automotive_workbench.project_workflow import load_project, run_project

ROOT = Path(__file__).resolve().parents[1]


class ProjectWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "source"
        shutil.copytree(ROOT / "examples/window_control", self.inputs)
        self.project = self.inputs / "project.json"
        self.output = self.root / "result"
        self.config = BusConfig("virtual", "project-" + uuid.uuid4().hex)

    def run_and_check(self, config=None):
        result = run_project(self.project, self.output, config or self.config)
        report = json.loads(Path(result["report_json"]).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "schemas/project-acceptance.schema.json").read_text()
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(report)
        self.assertEqual(result["integrity_status"], "passed")
        return result, report

    def test_project_runs_and_remains_verifiable_without_original_inputs(self):
        result, report = self.run_and_check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(report["requirements"]), 5)
        self.assertTrue(all(r["status"] == "passed" for r in report["requirements"]))
        shutil.rmtree(self.inputs)
        moved = self.root / "moved"
        shutil.copytree(self.output, moved)
        verified = verify_evidence_bundle(
            moved / "bundle", moved / "manifest.json", self.root / "recheck", base=moved
        )
        self.assertEqual(verified["status"], "passed")
        manifest = json.loads((moved / "manifest.json").read_text())
        self.assertTrue(
            all(
                dependency["kind"] == "artifact"
                for artifact in manifest["artifacts"]
                for dependency in artifact["depends_on"]
            )
        )
        (moved / "bundle/inputs/dbc.dbc").write_text("tampered")
        verified = verify_evidence_bundle(
            moved / "bundle",
            moved / "manifest.json",
            self.root / "tamper-check",
            base=moved,
        )
        self.assertEqual(verified["status"], "failed")

    def test_bad_configuration_stops_runtime_and_preserves_findings(self):
        path = self.inputs / "canonical_contract.json"
        payload = json.loads(path.read_text())
        payload["signals"][0]["resolution"] = "2"
        path.write_text(json.dumps(payload))
        with patch(
            "automotive_workbench.project_workflow.run_communication_chain"
        ) as runtime:
            result, report = self.run_and_check()
        runtime.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(report["stages"]["communication"]["status"], "skipped")
        findings = json.loads((self.output / "bundle/canonical.json").read_text())[
            "findings"
        ]
        self.assertTrue(any(f["code"] == "MAP-NUMERIC-MISMATCH" for f in findings))
        self.assertEqual(report["requirements"][-1]["status"], "blocked")

    def test_windows_bom_inputs_preserve_original_bytes(self):
        for name in ("project.json", "canonical_contract.json", "bsw_intent.json"):
            path = self.inputs / name
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        result, _ = self.run_and_check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            (self.output / "bundle/inputs/contract.json").read_bytes(),
            (self.inputs / "canonical_contract.json").read_bytes(),
        )

    def test_missing_backend_is_blocked_not_passed(self):
        result, report = self.run_and_check(
            BusConfig("socketcan", "absent-project-test")
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(report["requirements"][-1]["reason"], "backend_unavailable")

    def test_missing_evidence_and_boolean_number_do_not_pass(self):
        project = json.loads(self.project.read_text())
        project["name"] = '<script>alert("x")</script>'
        project["requirements"][0]["pointer"] = "/absent"
        project["requirements"][1]["pointer"] = "/finding_count"
        project["requirements"][1]["expected"] = False
        self.project.write_text(json.dumps(project))
        result, report = self.run_and_check()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(report["requirements"][0]["reason"], "evidence_missing")
        self.assertEqual(report["requirements"][1]["status"], "failed")
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_invalid_project_rejected_before_output_or_runtime(self):
        original = json.loads(self.project.read_text())
        mutations = [
            {**original, "schema_version": []},
            {**original, "command": "anything"},
            {**original, "requirements": []},
            {**original, "requirements": original["requirements"] * 2},
            {
                **original,
                "requirements": [{**original["requirements"][0], "stage": "shell"}],
            },
            {
                **original,
                "requirements": [{**original["requirements"][0], "pointer": "/~2"}],
            },
        ]
        for project in mutations:
            with self.subTest(project=project):
                self.project.write_text(json.dumps(project))
                with self.assertRaises(ValueError):
                    run_project(self.project, self.output, self.config)
                self.assertFalse(self.output.exists())
        self.project.write_text(json.dumps(original))
        load_project(self.project)
        self.output.mkdir()
        (self.output / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            run_project(self.project, self.output, self.config)
        self.assertEqual((self.output / "keep.txt").read_text(), "keep")
