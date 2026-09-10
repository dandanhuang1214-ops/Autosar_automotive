from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.communication_delivery import run_communication_delivery
from automotive_workbench.evidence_bundle import verify_evidence_bundle
from automotive_workbench.evidence_capsule import export_evidence_capsule


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceCapsuleTests(unittest.TestCase):
    def test_exports_and_verifies_without_using_original_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
            capsule = root / "relocated" / "capsule"

            result = export_evidence_capsule(delivery, capsule, base=ROOT)
            recheck = verify_evidence_bundle(
                capsule / "bundle",
                capsule / "manifest.json",
                root / "independent-recheck",
                base=capsule,
            )
            persisted = json.loads(
                (capsule / "evidence-capsule-report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, persisted)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["source_delivery_status"], "passed")
        self.assertEqual(
            (result["verified_artifact_count"], result["artifact_count"]), (7, 7)
        )
        self.assertEqual(
            (result["verified_dependency_count"], result["dependency_count"]),
            (3, 3),
        )
        self.assertEqual(result["external_dependency_count"], 2)
        self.assertEqual(result["copied_external_dependency_count"], 2)
        self.assertEqual(recheck["status"], "passed")
        self.assertEqual(
            {item["ref"] for item in result["external_dependencies"]},
            {
                "examples/window_control/bsw_intent.json",
                "examples/window_control/window_control.dbc",
            },
        )

    def test_rejects_missing_or_changed_external_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "source-base"
            source_dir = base / "inputs"
            source_dir.mkdir(parents=True)
            dbc = source_dir / "window.dbc"
            intent = source_dir / "intent.json"
            shutil.copy2(DBC, dbc)
            shutil.copy2(INTENT, intent)
            delivery = root / "delivery"
            run_communication_delivery(dbc, intent, delivery, base=base)
            intent.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "no longer passes"):
                export_evidence_capsule(delivery, root / "capsule", base=base)

        self.assertFalse((root / "capsule").exists())

    def test_exports_blocked_delivery_without_changing_its_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            run_communication_delivery(
                DBC,
                INTENT,
                delivery,
                BusConfig("socketcan", "workbench-definitely-missing"),
                base=ROOT,
            )
            result = export_evidence_capsule(
                delivery, root / "capsule", base=ROOT
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["source_delivery_status"], "blocked")
        self.assertEqual(
            result["verified_dependency_count"], result["dependency_count"]
        )

    def test_rejects_receipt_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
            receipt_path = delivery / "communication-evidence-delivery.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["manifest_sha256"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "manifest SHA-256"):
                export_evidence_capsule(delivery, root / "capsule", base=ROOT)

    def test_rejects_boolean_delivery_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
            receipt_path = delivery / "communication-evidence-delivery.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["dependency_count"] = False
            receipt["verified_dependency_count"] = False
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "count is invalid"):
                export_evidence_capsule(delivery, root / "capsule", base=ROOT)

    def test_rejects_nonempty_or_overlapping_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
            output = root / "capsule"
            output.mkdir()
            (output / "keep.txt").write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                export_evidence_capsule(delivery, output, base=ROOT)
            with self.assertRaisesRegex(ValueError, "overlap"):
                export_evidence_capsule(
                    delivery, delivery / "nested-capsule", base=ROOT
                )
            self.assertEqual((output / "keep.txt").read_text(), "keep\n")


if __name__ == "__main__":
    unittest.main()
