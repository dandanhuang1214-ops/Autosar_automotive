from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automotive_workbench.communication_delivery import run_communication_delivery
from automotive_workbench.evidence_capsule import export_evidence_capsule
from automotive_workbench.evidence_capsule_verification import verify_evidence_capsule
from scripts.evidence_capsule_tamper_exercise import check, prepare


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceCapsuleTamperExerciseTests(unittest.TestCase):
    def test_controlled_receipt_tamper_requires_cli_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = root / "delivery"
            capsule = root / "capsule"
            tampered = root / "tampered"
            output = root / "verification"
            run_communication_delivery(DBC, INTENT, delivery, base=ROOT)
            export_evidence_capsule(delivery, capsule, base=ROOT)
            prepare(capsule, tampered)
            verification = verify_evidence_capsule(tampered, output)
            result = check(output, "failure")

        self.assertEqual(verification["status"], "failed")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["finding_code"], "CAPSULE-SHA256-MISMATCH")

    def test_rejects_unexpected_successful_cli_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must be failure"):
                check(Path(directory), "success")


if __name__ == "__main__":
    unittest.main()
