"""Object protection behavior, contract parity and evidence replay."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from automotive_workbench.can_io import BusConfig
from automotive_workbench.ecuc_policy import evaluate
from automotive_workbench.ecuc_review import build
from automotive_workbench.ecuc_impact import compute
from automotive_workbench.project_ecuc import declaration, verify
from automotive_workbench.project_workflow import run_project
from automotive_workbench.project_comparison import compare_project_reports
from automotive_workbench.project_review import run_project_review

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ObjectPolicyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "inputs"
        shutil.copytree(ROOT / "examples/ecuc_acceptance", self.source)
        self.project = read(self.source / "integration.protected.project.json")
        shutil.copytree(self.source / "integration", self.source / "candidate")
        self.project["inputs"]["candidate"] = {
            k: [x.replace("integration/", "candidate/") for x in v]
            if isinstance(v, list)
            else v.replace("integration/", "candidate/")
            for k, v in self.project["inputs"]["candidate"].items()
        }

    def mutate(self, old, new):
        p = self.source / "candidate/modules.arxml"
        s = p.read_text()
        self.assertIn(old, s)
        p.write_text(s.replace(old, new, 1))

    def run_project(self, name="result"):
        path = self.source / "project.json"
        path.write_text(json.dumps(self.project))
        result = run_project(path, self.root / name, BusConfig("virtual", "unused"))
        report = Path(result["report_json"])
        for schema, data in [
            ("workbench-project", self.project),
            ("project-acceptance", read(report)),
            ("ecuc-project-acceptance", read(report.parent / "ecuc-stage.json")),
        ]:
            Draft202012Validator(read(ROOT / f"schemas/{schema}.schema.json")).validate(
                data
            )
        self.assertEqual(verify(report)["status"], "passed")
        return report

    def test_signal_change_is_rejected_with_both_values_and_exact_sources(self):
        self.mutate("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        report = self.run_project()
        self.assertEqual(read(report)["status"], "failed")
        row = read(report.parent / "ecuc-stage.json")["checks"]["policy.SIGNAL_SIZE"]
        self.assertEqual(row["reason"], "protected_field_changed")
        for side, expected in [("before", "8"), ("after", "12")]:
            obs = row["observations"][side]
            self.assertEqual(obs["values"], [expected])
            self.assertTrue(obs["field_pointers"])
            self.assertTrue(obs["object_pointers"])
        self.assertIn("ecuc:/Demo/Com/ValueA", row["affected_objects"])

    def test_valid_task_retargeting_fails_only_protected_reference(self):
        self.mutate("/Demo/Os/TaskA</VALUE-REF>", "/Demo/Os/TaskB</VALUE-REF>")
        report = self.run_project()
        checks = read(report.parent / "ecuc-stage.json")["checks"]
        self.assertEqual(checks["task_bindings"]["status"], "passed")
        self.assertEqual(checks["policy.TASK_REF"]["status"], "failed")
        self.assertEqual(checks["policy.TASK_PRESENT"]["status"], "passed")

    def test_policy_drift_without_requirement_drift_is_not_comparable(self):
        a = self.run_project("a")
        self.project["policies"][0]["object_id"] = "ecuc:/Demo/Com/PacketA"
        b = self.run_project("b")
        self.assertEqual(read(b)["status"], "passed")
        self.assertEqual(
            compare_project_reports(a, b, self.root / "compare")["status"],
            "not-comparable",
        )

    def test_explicitly_unprotected_known_change_passes(self):
        self.project["policies"] = [
            p for p in self.project["policies"] if p["id"] != "SIGNAL_SIZE"
        ]
        self.project["requirements"] = [
            r for r in self.project["requirements"] if r["id"] != "SIGNAL_SIZE"
        ]
        self.mutate("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        self.assertEqual(read(self.run_project())["status"], "passed")

    def test_protection_cannot_be_silently_omitted_from_acceptance(self):
        self.project["requirements"] = self.project["requirements"][:-1]
        with self.assertRaisesRegex(ValueError, "mandatory"):
            declaration(self.project)

    def test_invalid_policy_contract_rejected_by_schema_and_loader(self):
        schema = Draft202012Validator(
            read(ROOT / "schemas/workbench-project.schema.json")
        )
        for change in [
            {"object_id": "ValueA"},
            {"object_id": "ecuc:/Demo/*"},
            {"field_group": "vendor"},
            {"definition": "ComBitSize"},
            {"condition": "anything"},
            {"extra": True},
            {"definition": []},
        ]:
            project = copy.deepcopy(self.project)
            project["policies"][1].update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    declaration(project)
                with self.assertRaises(ValidationError):
                    schema.validate(project)

    def test_duplicate_policy_identity_is_rejected(self):
        self.project["policies"].append(copy.deepcopy(self.project["policies"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            declaration(self.project)

    def test_unknown_field_never_passes_even_when_unchanged_or_missing(self):
        self.project["policies"][1]["definition"] = "/Synthetic/ComSignal/VendorField"
        report = self.run_project()
        self.assertEqual(read(report)["status"], "unassessed")
        self.assertEqual(
            read(report.parent / "ecuc-stage.json")["checks"]["policy.SIGNAL_SIZE"][
                "reason"
            ],
            "unsupported_field",
        )

    def test_relocation_review_and_forged_observation_rejection(self):
        report = self.run_project()
        shutil.rmtree(self.source)
        report.parent.parent.rename(self.root / "moved")
        report = self.root / "moved/bundle/project-report.json"
        self.assertEqual(verify(report)["status"], "passed")
        self.assertEqual(
            run_project_review(report, self.root / "review")["status"], "answered"
        )
        stage = report.parent / "ecuc-stage.json"
        data = read(stage)
        data["checks"]["policy.SIGNAL_SIZE"]["observations"]["before"]["values"] = [
            "forged"
        ]
        stage.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "stage differs"):
            verify(report)

    def test_missing_ambiguous_conditional_and_unsupported_objects(self):
        before, _ = build(
            self.source / "integration/demo.dpa",
            [self.source / "integration/application.arxml"],
            [],
        )
        identity = self.project["policies"][0]["object_id"]
        for case, expected in [
            ("missing", "failed"),
            ("duplicate", "blocked"),
            ("conditional", "unassessed"),
            ("unsupported", "unassessed"),
        ]:
            after = copy.deepcopy(before)
            obj = next(o for o in after["objects"] if o["id"] == identity)
            if case == "missing":
                after["objects"].remove(obj)
            elif case == "duplicate":
                after["objects"].append(copy.deepcopy(obj))
            elif case == "conditional":
                obj["conditional"] = True
            else:
                obj["type"] = "VendorUnknown"
            impact = compute(before, after, "a" * 64, "b" * 64)
            with self.subTest(case=case):
                self.assertEqual(
                    evaluate(self.project["policies"][0], before, after, impact)[
                        "status"
                    ],
                    expected,
                )

    def test_structure_gap_is_rejected_by_object_policy_without_global_checks(self):
        self.project["requirements"] = [
            r for r in self.project["requirements"] if r["id"] == "SIGNAL_PRESENT"
        ]
        self.project["policies"] = self.project["policies"][:1]
        self.mutate("/Demo/EcuC/C</VALUE-REF>", "/Demo/EcuC/Missing</VALUE-REF>")
        report = self.run_project()
        self.assertEqual(read(report)["status"], "failed")
        row = read(report.parent / "ecuc-stage.json")["checks"]["policy.SIGNAL_PRESENT"]
        self.assertEqual(row["reason"], "structural_gap")
        self.assertTrue(row["observations"]["after"]["witness_pointers"])

    def test_field_missing_duplicate_conditional_and_dangling_reference(self):
        before, _ = build(
            self.source / "integration/demo.dpa",
            [self.source / "integration/application.arxml"],
            [],
        )
        for case, expected in [
            ("missing", "failed"),
            ("duplicate", "blocked"),
            ("conditional", "unassessed"),
            ("dangling", "failed"),
        ]:
            policy = self.project["policies"][2 if case == "dangling" else 1]
            after = copy.deepcopy(before)
            obj = next(o for o in after["objects"] if o["id"] == policy["object_id"])
            fields = obj[policy["field_group"]]
            field = next(f for f in fields if f["definition"] == policy["definition"])
            if case == "missing":
                fields.remove(field)
            elif case == "duplicate":
                fields.append(copy.deepcopy(field))
            elif case == "conditional":
                field["conditional"] = True
            else:
                field["target"] = "/Absent/Task"
            impact = compute(before, after, "a" * 64, "b" * 64)
            with self.subTest(case=case):
                self.assertEqual(
                    evaluate(policy, before, after, impact)["status"], expected
                )

    def test_unknown_scope_blocks_policy_only_acceptance(self):
        self.project["requirements"] = [
            r for r in self.project["requirements"] if r["id"] == "SIGNAL_SIZE"
        ]
        self.project["policies"] = self.project["policies"][1:2]
        self.mutate(
            "<SHORT-NAME>TaskA</SHORT-NAME>",
            "<SHORT-NAME>TaskA</SHORT-NAME><VENDOR>unknown</VENDOR>",
        )
        self.assertEqual(read(self.run_project())["status"], "unassessed")

    def test_mode_rule_protection_and_missing_application_boundary(self):
        self.project["policies"] = [
            {
                "id": "MODE",
                "object_id": "ecuc:/Demo/BswM/Rule",
                "condition": "exists_complete",
            }
        ]
        self.project["requirements"] = [
            {
                "id": "MODE",
                "text": "Protect mode structure",
                "stage": "ecuc",
                "pointer": "/checks/policy.MODE/status",
                "expected": "passed",
            }
        ]
        self.assertEqual(read(self.run_project("mode"))["status"], "passed")
        self.project["policies"][0].update(object_id="ecuc:/Demo/Rte/Instance/Mapping")
        self.project["inputs"]["candidate"]["applications"] = []
        self.assertEqual(read(self.run_project("missing"))["status"], "unassessed")

    def test_case_distinct_policy_ids_have_distinct_review_assertions(self):
        policy = copy.deepcopy(self.project["policies"][0])
        policy["id"] = "signal_present"
        self.project["policies"].append(policy)
        requirement = copy.deepcopy(self.project["requirements"][-1])
        requirement.update(
            id="SECOND_PROTECTION", pointer="/checks/policy.signal_present/status"
        )
        self.project["requirements"].append(requirement)
        report = self.run_project()
        self.assertEqual(
            run_project_review(report, self.root / "review")["status"], "answered"
        )
