from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    verify_evidence_bundle,
)
from scripts.evidence_bundle_tamper_exercise import (
    check_tamper_rejection,
    prepare_tampered_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceBundleTamperExerciseTests(unittest.TestCase):
    def test_controlled_tamper_requires_cli_failure_and_closed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "communication"
            run_communication_chain(DBC, INTENT, bundle)
            manifest = root / "manifest.json"
            create_evidence_bundle_manifest(bundle, manifest, "test", base=ROOT)
            tampered = root / "tampered"
            preparation = prepare_tampered_bundle(bundle, tampered)
            output = root / "rejection"
            result = verify_evidence_bundle(tampered, manifest, output, base=ROOT)
            summary = check_tamper_rejection(output, "failure")

        self.assertEqual(preparation["tampered_path"], "runtime/can-runtime-report.json")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["reason_code"], "EVIDENCE-SIZE-MISMATCH")

    def test_unexpected_cli_success_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must be failure"):
                check_tamper_rejection(Path(directory), "success")


if __name__ == "__main__":
    unittest.main()
