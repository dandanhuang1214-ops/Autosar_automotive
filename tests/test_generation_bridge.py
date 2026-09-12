from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.cli import main
from automotive_workbench.project_workflow import load_project, run_project
from automotive_workbench.evidence_bundle import verify_evidence_bundle
from scripts.create_public_delivery_docx import create_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/generate_arxml/bridge"


class GenerationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = BusConfig("virtual", "generation-bridge")

    def copy_case(self, name):
        dest = self.root / name
        shutil.copytree(FIXTURES / name, dest)
        return dest

    def read_report(self, result):
        report = json.loads(Path(result["report_json"]).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "schemas/project-acceptance.schema.json").read_text()
        )
        Draft202012Validator(schema).validate(report)
        self.assertEqual(result["integrity_status"], "passed")
        return report

    def test_real_export_normal_and_configuration_failure_preserve_upstream_findings(
        self,
    ):
        for name, expected, generation, canonical in [
            ("baseline", "passed", "passed", "passed"),
            ("scale-change", "failed", "passed", "failed"),
            ("missing-init", "failed", "failed", "passed"),
        ]:
            with self.subTest(name=name):
                case = self.copy_case(name)
                result = run_project(
                    case / "project.json", self.root / (name + "-out"), self.config
                )
                report = self.read_report(result)
                self.assertEqual(result["status"], expected)
                self.assertEqual(report["stages"]["generation"]["status"], generation)
                self.assertEqual(report["stages"]["canonical"]["status"], canonical)
                gate = json.loads(
                    (Path(result["report_json"]).parent / "generation.json").read_text()
                )
                original = json.loads((case / "issues.json").read_text())
                self.assertEqual(gate["findings"], original["items"])
                self.assertEqual(gate["warning_count"], 3 if name == "scale-change" else 2)
                self.assertFalse(gate["producer_identity_verified"])
                if expected == "failed":
                    self.assertEqual(
                        report["stages"]["communication"]["status"], "skipped"
                    )
                    self.assertFalse(
                        (Path(result["report_json"]).parent / "communication").exists()
                    )
                else:
                    self.assertTrue(
                        all(r["status"] == "passed" for r in report["requirements"])
                    )

    def test_upstream_rejection_cannot_be_hidden_by_exit_zero_or_successful_static_checks(
        self,
    ):
        case = self.copy_case("missing-init")
        project = json.loads((case / "project.json").read_text())
        project["generation"]["exit_code"] = 0
        project["requirements"] = [project["requirements"][1]]
        (case / "project.json").write_text(json.dumps(project))
        with patch(
            "automotive_workbench.project_workflow.run_communication_chain"
        ) as runtime:
            result = run_project(case / "project.json", self.root / "out", self.config)
        runtime.assert_not_called()
        self.assertEqual(result["status"], "failed")

    def test_stale_contract_docx_or_issue_report_rejected_before_output(self):
        for name in ("contract.json", "source.docx", "issues.json"):
            with self.subTest(name=name):
                case = self.root / name.replace(".", "-")
                shutil.copytree(FIXTURES / "baseline", case)
                with (case / name).open("ab") as file:
                    file.write(b" ")
                output = case / "out"
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    run_project(case / "project.json", output, self.config)
                self.assertFalse(output.exists())

    def test_invalid_generation_declarations_and_reports_fail_closed(self):
        case = self.copy_case("baseline")
        path = case / "project.json"
        original = json.loads(path.read_text())
        for change in (
            {"exit_code": True},
            {"revision": "main"},
            {"tool": "shell"},
            {"command": "echo"},
        ):
            project = {**original, "generation": {**original["generation"], **change}}
            path.write_text(json.dumps(project))
            schema = json.loads(
                (ROOT / "schemas/workbench-project.schema.json").read_text()
            )
            self.assertFalse(Draft202012Validator(schema).is_valid(project))
            with self.assertRaises(ValueError):
                load_project(path)
        for mutation in ("summary", "items", "count"):
            report = json.loads((FIXTURES / "baseline/issues.json").read_text())
            if mutation == "summary":
                report["core_summary"]["by_severity"]["ERROR"] = False
            elif mutation == "items":
                report["items"].append("invalid finding")
            else:
                report["counts"]["signals"] = 1
            (case / "issues.json").write_text(json.dumps(report))
            project = json.loads(json.dumps(original))
            project["generation"]["sha256"]["issue_report"] = sha256_file(
                case / "issues.json"
            )
            path.write_text(json.dumps(project))
            with self.assertRaises(ValueError):
                load_project(path)

    def test_docx_source_reproduction_and_portable_snapshot(self):
        for name, resolution, omit_init in [
            ("baseline", "1", False),
            ("scale-change", "2", False),
            ("missing-init", "1", True),
        ]:
            path = self.root / (name + ".docx")
            create_document(path, resolution=resolution, omit_init=omit_init)
            self.assertEqual(
                path.read_bytes(), (FIXTURES / name / "source.docx").read_bytes()
            )
        case = self.copy_case("baseline")
        output = self.root / "out"
        run_project(case / "project.json", output, self.config)
        shutil.rmtree(case)
        moved = self.root / "moved"
        shutil.copytree(output, moved)
        result = verify_evidence_bundle(
            moved / "bundle", moved / "manifest.json", self.root / "recheck", base=moved
        )
        self.assertEqual(result["status"], "passed")
        (moved / "bundle/inputs/source.docx").write_bytes(b"tampered")
        result = verify_evidence_bundle(
            moved / "bundle", moved / "manifest.json", self.root / "tamper", base=moved
        )
        self.assertEqual(result["status"], "failed")

    def test_cli_exit_codes_for_imported_exports(self):
        for name, code in [("baseline", 0), ("scale-change", 2), ("missing-init", 2)]:
            args = [
                "workbench",
                "run-project",
                str(FIXTURES / name / "project.json"),
                "--output",
                str(self.root / name),
            ]
            with patch("sys.argv", args), patch("builtins.print"):
                self.assertEqual(main(), code)
