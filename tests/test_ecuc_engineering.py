from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from automotive_workbench.ecuc_impact import compare_reviews, compute, verify_impact
from automotive_workbench.ecuc_review import (
    build,
    read_verified,
    run_review,
    verify_review,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/ecuc-engineering"


class EcucEngineeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        shutil.copytree(FIXTURE, self.source)
        self.project = self.source / "demo.dpa"
        self.app = self.source / "application.arxml"
        self.log = self.source / "tool.log"
        self.schemas = {
            name: Draft202012Validator(
                json.loads(
                    (ROOT / "schemas" / (name + ".schema.json")).read_text(
                        encoding="utf-8"
                    )
                )
            )
            for name in ["ecuc-engineering-review", "ecuc-configuration-impact"]
        }

    def report(self):
        report = build(self.project, [self.app], [self.log])[0]
        self.schemas["ecuc-engineering-review"].validate(report)
        return report

    def change(self, before: str, after: str, file: str = "modules.arxml") -> None:
        path = self.source / file
        value = path.read_text(encoding="utf-8")
        self.assertIn(before, value)
        path.write_text(value.replace(before, after), encoding="utf-8")

    def delta(self, before):
        result = compute(before, self.report(), "a" * 64, "b" * 64)
        self.schemas["ecuc-configuration-impact"].validate(result)
        return result

    def test_complete_integration_keeps_historical_errors_separate(self) -> None:
        r = self.report()
        self.assertEqual(r["status"], "no-issues-in-scope")
        self.assertEqual(r["summary"]["structural_findings"], 0)
        self.assertEqual(r["summary"]["task_bindings"], 2)
        self.assertTrue(
            all(x["status"] == "linked-in-scope" for x in r["integration"]["bindings"])
        )
        self.assertEqual(r["historical_tool_logs"][0]["binding"], "historical-unbound")
        self.assertEqual(
            [x["association"] for x in r["historical_tool_logs"][0]["records"]],
            ["exact-path", "unassessed", "unassessed"],
        )
        self.assertEqual(
            r["integration"]["coverage"]["timing_and_runtime"], "unassessed"
        )
        self.assertIn(
            "application:/App/Worker", r["integration"]["applications"][0]["types"]
        )

    def test_no_application_inputs_remain_unassessed(self) -> None:
        r = build(self.project, [], [self.log])[0]
        self.assertEqual(r["status"], "attention-required")
        self.assertEqual(r["integration"]["coverage"]["application"], "unassessed")
        self.assertTrue(
            all(x["status"] == "partial" for x in r["integration"]["bindings"])
        )

    def test_missing_wrong_and_conditional_task_references(self) -> None:
        for target, expected in [
            ("/Demo/Os/Absent", "missing"),
            ("/Demo/Os/EventA", "wrong-type"),
            ("", "empty"),
            ("/Outside/Task", "unassessed"),
        ]:
            with self.subTest(target=target):
                (self.source / "modules.arxml").write_bytes(
                    (FIXTURE / "modules.arxml").read_bytes()
                )
                self.change("/Demo/Os/TaskA", target)
                r = self.report()
                self.assertEqual(r["integration"]["bindings"][0]["status"], "partial")
                self.assertEqual(
                    r["integration"]["bindings"][1]["status"], "linked-in-scope"
                )
                edge = next(
                    e
                    for e in r["integration"]["dependencies"]
                    if e["role"] == "RteMappedToTaskRef"
                )
                self.assertEqual(edge["resolution"], expected)
        (self.source / "modules.arxml").write_bytes(
            (FIXTURE / "modules.arxml").read_bytes()
        )
        self.change(
            "<SHORT-NAME>TaskA</SHORT-NAME>",
            "<SHORT-NAME>TaskA</SHORT-NAME><VARIATION-POINT/>",
        )
        self.assertEqual(
            self.report()["integration"]["bindings"][0]["status"], "partial"
        )

    def test_component_and_behavior_ownership_are_checked(self) -> None:
        self.change(
            "/App/Worker</TYPE-TREF>", "/App/Basic</TYPE-TREF>", "application.arxml"
        )
        self.assertEqual(
            self.report()["integration"]["applications"][0]["status"], "partial"
        )
        self.app.write_bytes((FIXTURE / "application.arxml").read_bytes())
        self.change(
            "/App/Worker/Behavior/Run", "/App/Basic/Behavior/Run", "application.arxml"
        )
        self.assertEqual(
            self.report()["integration"]["bindings"][0]["status"], "partial"
        )

    def test_mode_missing_target_and_cycle_are_explicit(self) -> None:
        self.change("/Demo/BswM/Expression", "/Demo/BswM/Missing")
        self.assertEqual(
            self.report()["integration"]["mode_rules"][0]["status"], "partial"
        )
        (self.source / "modules.arxml").write_bytes(
            (FIXTURE / "modules.arxml").read_bytes()
        )
        self.change("/Demo/BswM/Action</VALUE-REF>", "/Demo/BswM/Rule</VALUE-REF>")
        row = self.report()["integration"]["mode_rules"][0]
        self.assertEqual(row["status"], "partial")
        self.assertTrue(any("cycle" in g for g in row["gaps"]))

    def test_signal_change_targets_tx_only_and_provides_witness(self) -> None:
        before = self.report()
        self.change("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        delta = self.delta(before)
        self.assertEqual(delta["status"], "changed-in-scope")
        self.assertEqual(
            [x["object_id"] for x in delta["changes"]], ["ecuc:/Demo/Com/ValueA"]
        )
        self.assertEqual(
            {x["com_ipdu"] for x in delta["communication_impacts"]},
            {"/Demo/Com/PacketA"},
        )
        self.assertFalse(delta["binding_impacts"])
        self.assertFalse(delta["mode_impacts"])
        ipdu = next(
            x
            for x in delta["affected_objects"]
            if x["object_id"] == "ecuc:/Demo/Com/PacketA"
        )
        self.assertTrue(ipdu["dependency_edges"])
        self.assertEqual(ipdu["origin"], "ecuc:/Demo/Com/ValueA")

    def test_task_rebinding_and_priority_change_are_scoped(self) -> None:
        before = self.report()
        self.change("/Demo/Os/TaskA</VALUE-REF>", "/Demo/Os/TaskB</VALUE-REF>")
        delta = self.delta(before)
        self.assertEqual(
            {x["mapping"] for x in delta["binding_impacts"]},
            {"ecuc:/Demo/Rte/Instance/Mapping"},
        )
        self.assertFalse(delta["communication_impacts"])
        (self.source / "modules.arxml").write_bytes(
            (FIXTURE / "modules.arxml").read_bytes()
        )
        self.change("<VALUE>5</VALUE>", "<VALUE>6</VALUE>")
        delta = self.delta(before)
        self.assertEqual(
            {x["mapping"] for x in delta["binding_impacts"]},
            {"ecuc:/Demo/Rte/Instance/Mapping"},
        )

    def test_application_period_and_mode_changes_have_separate_impact(self) -> None:
        before = self.report()
        self.change(
            "<PERIOD>0.010</PERIOD>", "<PERIOD>0.020</PERIOD>", "application.arxml"
        )
        delta = self.delta(before)
        self.assertEqual(len(delta["changes"]), 2)
        self.assertEqual(len({x["mapping"] for x in delta["binding_impacts"]}), 2)
        self.assertFalse(delta["communication_impacts"])
        self.app.write_bytes((FIXTURE / "application.arxml").read_bytes())
        self.change("BSWM_EQUALS", "BSWM_EQUALS_NOT")
        delta = self.delta(before)
        self.assertEqual(
            {x["rule"] for x in delta["mode_impacts"]}, {"ecuc:/Demo/BswM/Rule"}
        )
        self.assertFalse(delta["binding_impacts"])

    def test_opaque_changes_are_not_called_stable_or_no_impact(self) -> None:
        before = self.report()
        self.change(
            "<SHORT-NAME>ValueA</SHORT-NAME>",
            "<SHORT-NAME>ValueA</SHORT-NAME><VENDOR-EXTENSION>new</VENDOR-EXTENSION>",
        )
        delta = self.delta(before)
        self.assertEqual(delta["status"], "partial")
        self.assertTrue(delta["unassessed_changes"])
        self.assertTrue(delta["communication_impacts"])

    def test_duplicate_objects_and_disjoint_scopes_are_not_comparable(self) -> None:
        before = self.report()
        self.change("<SHORT-NAME>TaskB</SHORT-NAME>", "<SHORT-NAME>TaskA</SHORT-NAME>")
        delta = self.delta(before)
        self.assertEqual(delta["status"], "not-comparable")
        self.assertFalse(delta["changes"])
        other = copy.deepcopy(before)
        other["selected_modules"] = ["/Unrelated/Module"]
        self.assertEqual(
            compute(before, other, "a" * 64, "b" * 64)["status"], "not-comparable"
        )

    def test_formatting_and_log_only_change_are_not_configuration_change(self) -> None:
        before = self.report()
        self.change("    <AR-PACKAGE>", "  <AR-PACKAGE>")
        self.log.write_text(
            "INFO NEW [/Demo/Os/TaskA] Later historical observation\n", encoding="utf-8"
        )
        delta = self.delta(before)
        self.assertEqual(delta["status"], "unchanged-in-scope")
        self.assertTrue(delta["historical_logs_changed"])
        self.assertFalse(delta["changes"])

    def test_removed_signal_reaches_old_path_without_guessing_new_path(self) -> None:
        before = self.report()
        self.change(
            "<SHORT-NAME>ValueA</SHORT-NAME>", "<SHORT-NAME>Renamed</SHORT-NAME>"
        )
        delta = self.delta(before)
        self.assertEqual({x["kind"] for x in delta["changes"]}, {"added", "removed"})
        self.assertIn("before", {x["snapshot"] for x in delta["communication_impacts"]})
        self.assertEqual(self.report()["communication"]["status"], "partial")

    def test_review_and_comparison_survive_relocation_without_originals(self) -> None:
        a, b = self.root / "a", self.root / "b"
        run_review(self.project, a, [self.app], [self.log])
        self.change("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        run_review(self.project, b, [self.app], [self.log])
        out = self.root / "impact"
        compare_reviews(a / "ecuc-review.json", b / "ecuc-review.json", out)
        shutil.rmtree(self.source)
        shutil.rmtree(a)
        shutil.rmtree(b)
        moved = self.root / "moved"
        out.rename(moved)
        self.assertEqual(verify_impact(moved / "ecuc-impact.json")["status"], "passed")
        self.assertEqual(
            verify_review(moved / "before/ecuc-review.json")["status"], "passed"
        )
        original = (moved / "ecuc-impact.json").read_bytes()
        r = json.loads(original)
        r["affected_objects"] = []
        (moved / "ecuc-impact.json").write_text(json.dumps(r), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_impact(moved / "ecuc-impact.json")
        (moved / "ecuc-impact.json").write_bytes(original)
        (moved / "before/index.html").write_text("forged", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "HTML"):
            verify_impact(moved / "ecuc-impact.json")

    def test_source_inventory_and_log_tampering_are_rejected(self) -> None:
        out = self.root / "review"
        run_review(self.project, out, [self.app], [self.log])
        extra = out / "snapshot/extra.txt"
        extra.write_text("extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            read_verified(out / "ecuc-review.json")
        extra.unlink()
        log = out / "snapshot/tool-logs/0000.log"
        log.write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            read_verified(out / "ecuc-review.json")

    def test_html_escapes_logs_and_output_is_protected(self) -> None:
        self.log.write_text(
            "ERROR SCRIPT [/Demo/Os/TaskA] <script>alert(1)</script>\n",
            encoding="utf-8",
        )
        out = self.root / "review"
        run_review(self.project, out, [self.app], [self.log])
        markup = (out / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)
        with self.assertRaisesRegex(ValueError, "empty"):
            run_review(self.project, out, [self.app], [])
        with self.assertRaisesRegex(ValueError, "outside"):
            run_review(self.project, self.source / "out")
        with self.assertRaisesRegex(ValueError, "overlap"):
            compare_reviews(
                out / "ecuc-review.json", out / "ecuc-review.json", out / "nested"
            )

    def test_mixed_unknown_xml_text_is_not_silently_ignored(self) -> None:
        self.change(
            "<SHORT-NAME>ValueA</SHORT-NAME>",
            "<SHORT-NAME>ValueA</SHORT-NAME><VENDOR>prefix<X/>tail</VENDOR>",
        )
        before = self.report()
        self.change("tail</VENDOR>", "changed</VENDOR>")
        delta = self.delta(before)
        self.assertEqual(delta["status"], "partial")
        self.assertTrue(delta["unassessed_changes"])

    def test_vendor_parameter_value_change_remains_unassessed(self) -> None:
        self.change("ComBitSize", "VendorWidth")
        before = self.report()
        self.change("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        delta = self.delta(before)
        self.assertEqual(delta["status"], "partial")
        self.assertTrue(delta["unassessed_changes"])
        self.assertEqual(
            {p["com_ipdu"] for p in delta["communication_impacts"]},
            {"/Demo/Com/PacketA"},
        )
