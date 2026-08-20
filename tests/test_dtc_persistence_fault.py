from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_persistence_fault import run_dtc_persistence_fault_lab


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcPersistenceFaultTests(unittest.TestCase):
    def test_runs_flush_failure_and_corrupt_restore_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_persistence_fault_lab(INTENT, output)
            persisted = json.loads(
                (output / "dtc-persistence-fault-report.json").read_text(encoding="utf-8")
            )
            markdown = (output / "dtc-persistence-fault-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 13)
        self.assertEqual(result["expected_fault_count"], 3)
        self.assertEqual(result["finding_count"], 3)
        self.assertEqual(result["traces"][4]["actual_finding"], "DTC-PERSISTENCE-FLUSH-FAILED")
        self.assertTrue(result["traces"][4]["mirror_integrity"])
        self.assertEqual(result["traces"][5]["runtime_status_hex"], "0x00")
        self.assertEqual(
            result["traces"][11]["actual_finding"],
            "DTC-PERSISTENCE-MIRROR-CORRUPTED",
        )
        self.assertFalse(result["traces"][11]["mirror_integrity"])
        self.assertEqual(
            result["traces"][12]["actual_finding"],
            "DTC-PERSISTENCE-RESTORE-FAILED",
        )
        self.assertEqual(result["traces"][12]["runtime_status_hex"], "0x00")
        self.assertEqual(result["traces"][12]["persistent_status_hex"], "0x2F")
        self.assertEqual(persisted["artifact_type"], "dtc-persistence-fault-lab")
        self.assertIn("not AUTOSAR NvM", markdown)

    def test_reports_mismatched_expected_finding(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["persistence_fault_experiments"][0]["steps"][4]["expected_finding"] = ""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dtc_persistence_fault_lab(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["traces"][4]["status"], "failed")
        self.assertEqual(result["traces"][4]["actual_finding"], "DTC-PERSISTENCE-FLUSH-FAILED")


if __name__ == "__main__":
    unittest.main()
