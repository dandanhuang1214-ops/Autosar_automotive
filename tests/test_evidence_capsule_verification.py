from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from automotive_workbench.communication_delivery import run_communication_delivery
from automotive_workbench.evidence_capsule import export_evidence_capsule
from automotive_workbench.evidence_capsule_verification import verify_evidence_capsule


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceCapsuleVerificationTests(unittest.TestCase):
    @staticmethod
    def _capsule(root: Path) -> Path:
        delivery = root / "delivery"
        capsule = root / "capsule"
        run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
        export_evidence_capsule(delivery, capsule, base=ROOT)
        return capsule

    def test_verifies_complete_capsule_inventory_and_dependency_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            result = verify_evidence_capsule(capsule, root / "verification")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            (result["verified_file_count"], result["expected_file_count"]),
            (16, 16),
        )
        self.assertEqual(
            (result["verified_artifact_count"], result["artifact_count"]), (7, 7)
        )
        self.assertEqual(
            (result["verified_dependency_count"], result["dependency_count"]),
            (3, 3),
        )
        self.assertEqual(result["findings"], [])

    def test_reports_external_dependency_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            target = capsule / "examples" / "window_control" / "window_control.dbc"
            content = target.read_bytes()
            target.write_bytes(bytes([content[0] ^ 1]) + content[1:])
            result = verify_evidence_capsule(capsule, root / "verification")

        self.assertEqual(result["status"], "failed")
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("CAPSULE-SHA256-MISMATCH", codes)
        self.assertIn("CAPSULE-CONTENT-VERIFICATION-FAILED", codes)
        self.assertEqual(result["verified_dependency_count"], 2)

    def test_reports_missing_receipt_and_unexpected_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            (capsule / "communication-evidence-delivery.json").unlink()
            (capsule / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            result = verify_evidence_capsule(capsule, root / "verification")

        codes = {item["code"] for item in result["findings"]}
        self.assertEqual(result["status"], "failed")
        self.assertIn("CAPSULE-FILE-MISSING", codes)
        self.assertIn("CAPSULE-FILE-UNEXPECTED", codes)

    def test_reports_derived_markdown_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            report = capsule / "evidence-capsule-report.md"
            report.write_text("changed\n", encoding="utf-8")
            result = verify_evidence_capsule(capsule, root / "verification")

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "CAPSULE-SHA256-MISMATCH",
            {item["code"] for item in result["findings"]},
        )

    def test_reports_symlink_and_rejects_output_inside_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            target = capsule / "examples" / "window_control" / "bsw_intent.json"
            target.unlink()
            try:
                target.symlink_to(INTENT)
            except OSError:
                self.skipTest("symlinks are not available on this platform")
            result = verify_evidence_capsule(capsule, root / "verification")
            with self.assertRaisesRegex(ValueError, "outside"):
                verify_evidence_capsule(capsule, capsule / "verification-result")

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "CAPSULE-SYMLINK-DETECTED",
            {item["code"] for item in result["findings"]},
        )

    def test_rejects_boolean_capsule_report_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            report_path = capsule / "evidence-capsule-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["dependency_count"] = False
            report["verified_dependency_count"] = False
            report_path.write_text(json.dumps(report), encoding="utf-8")

            schema = json.loads(
                (ROOT / "schemas" / "evidence-capsule.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(list(validator_for(schema)(schema).iter_errors(report)))

            with self.assertRaisesRegex(ValueError, "count is invalid"):
                verify_evidence_capsule(capsule, root / "verification")

    def test_schema_and_loader_reject_invalid_capsule_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = self._capsule(root)
            report_path = capsule / "evidence-capsule-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["created_at"] = "not-a-date-time"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            schema = json.loads(
                (ROOT / "schemas" / "evidence-capsule.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            validator = validator_for(schema)(schema, format_checker=FormatChecker())
            self.assertTrue(list(validator.iter_errors(report)))
            with self.assertRaisesRegex(ValueError, "RFC 3339"):
                verify_evidence_capsule(capsule, root / "verification")


if __name__ == "__main__":
    unittest.main()
