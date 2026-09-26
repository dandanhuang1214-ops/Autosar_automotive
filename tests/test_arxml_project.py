from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.arxml_bridge import digest
from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.project_workflow import load_project, run_project
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import compare_project_reports
from scripts.run_arxml_scenarios import mutations

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class ArxmlProjectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.project = self.source / "project.json"
        project = read(ROOT / "examples/window_control/project-arxml.json")
        for key, value in list(project["inputs"].items()):
            path = ROOT / "examples/window_control" / value
            shutil.copyfile(path, self.source / path.name)
            project["inputs"][key] = path.name
        write(self.project, project)
        self.xml = self.source / "model.arxml"
        self.original = self.xml.read_bytes()
        schemas = [read(p) for p in (ROOT / "schemas").glob("*.json")]
        self.registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in schemas
        )

    def schema(self, name, value):
        Draft202012Validator(
            read(ROOT / "schemas" / (name + ".schema.json")), registry=self.registry
        ).validate(value)

    def mutate(self, data):
        self.xml.write_bytes(data)
        write(
            self.source / "provenance.json",
            {"status": "synthetic-mutation", "arxml_sha256": digest(data)},
        )

    def run_case(self, name):
        result = run_project(
            self.project, self.root / name, default_communication_config()
        )
        path = Path(result["report_json"])
        self.assertEqual(result["integrity_status"], "passed")
        self.schema("project-acceptance", read(path))
        self.schema("arxml-project-gate", read(path.parent / "arxml.json"))
        return path

    def test_normal_schema_review_and_stable_comparison(self):
        self.schema("workbench-project", load_project(self.project)[0])
        report = self.run_case("normal")
        self.assertEqual(read(report)["status"], "passed")
        review = run_project_review(report, self.root / "review")
        self.assertEqual(review["status"], "answered")
        self.assertIn("STAGE-ARXML", json.dumps(review))
        self.assertEqual(
            compare_project_reports(report, report, self.root / "comparison")["status"],
            "stable",
        )

    def test_dangling_and_unsupported_never_open_bus(self):
        for name, data in {
            "dangling": mutations(self.original)["dangling"],
            "unsupported": self.original.replace(
                b"</AUTOSAR>", b"<UNKNOWN-ELEMENT/></AUTOSAR>"
            ),
        }.items():
            self.mutate(data)
            with patch(
                "automotive_workbench.project_workflow.run_bound_communication"
            ) as runtime:
                report = self.run_case(name)
            runtime.assert_not_called()
            self.assertEqual(read(report)["status"], "failed")
            self.assertEqual(
                read(report)["stages"]["communication"]["status"], "skipped"
            )
            review = run_project_review(report, self.root / (name + "-review"))
            self.assertEqual(review["status"], "answered")
            self.assertIn("ERROR", json.dumps(review))

    def test_malformed_xml_and_provenance_rejected_before_output(self):
        for name, data, update in [
            ("xml", b"<broken", True),
            ("hash", self.original + b"\n", False),
        ]:
            if update:
                self.mutate(data)
            else:
                self.xml.write_bytes(data)
            with (
                self.assertRaises(ValueError),
                patch(
                    "automotive_workbench.project_workflow.run_bound_communication"
                ) as runtime,
            ):
                run_project(
                    self.project, self.root / name, default_communication_config()
                )
            runtime.assert_not_called()
            self.assertFalse((self.root / name).exists())

    def test_semantic_change_cannot_be_reported_as_stable(self):
        normal = self.run_case("normal")
        self.mutate(mutations(self.original)["period-change"])
        changed = self.run_case("changed")
        result = compare_project_reports(normal, changed, self.root / "comparison")
        self.assertEqual(result["status"], "not-comparable")
        self.assertIn("project comparison basis differs", result["basis"]["reasons"])
        self.mutate(self.original + b"\n")
        formatted = self.run_case("formatted")
        self.assertEqual(
            compare_project_reports(normal, formatted, self.root / "format-comparison")[
                "status"
            ],
            "stable",
        )

    def test_schema_loader_version_parity(self):
        original = read(self.project)
        for name in ("old", "missing", "extra"):
            value = copy.deepcopy(original)
            if name == "old":
                value["schema_version"] = "workbench-project-0.3"
            elif name == "missing":
                del value["inputs"]["provenance"]
            else:
                value["inputs"]["extra"] = "x"
            write(self.project, value)
            validator = Draft202012Validator(
                read(ROOT / "schemas/workbench-project.schema.json")
            )
            self.assertFalse(validator.is_valid(value))
            with self.assertRaises(ValueError):
                load_project(self.project)

    def test_replay_rejects_tamper_even_if_inventory_hash_is_updated(self):
        path = self.run_case("normal")
        target = path.parent / "arxml.json"
        gate = read(target)
        gate["import"]["objects"][0]["kind"] = "FORGED"
        write(target, gate)
        report = read(path)
        for item in report["source_artifacts"]:
            if item["source"] == "bundle/arxml.json":
                item["sha256"] = digest(target.read_bytes())
        write(path, report)
        with self.assertRaisesRegex(ValueError, "ARXML report disagrees"):
            run_project_review(path, self.root / "review")
        self.assertFalse((self.root / "review").exists())


if __name__ == "__main__":
    unittest.main()
