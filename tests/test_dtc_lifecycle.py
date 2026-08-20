from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_lifecycle import run_dtc_lifecycle


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcLifecycleTests(unittest.TestCase):
    def test_runs_fault_confirm_heal_read_clear_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_lifecycle(INTENT, output)
            persisted = json.loads(
                (output / "dtc-lifecycle-report.json").read_text(encoding="utf-8")
            )
            markdown = (output / "dtc-lifecycle-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 8)
        self.assertEqual(result["finding_count"], 0)
        states = [item["observed_state"] for item in result["traces"]]
        self.assertEqual(
            states,
            ["absent", "pending", "confirmed", "healing", "healed", "healed", "absent", "absent"],
        )
        self.assertEqual(result["traces"][5]["request_payload_hex"], "190208")
        self.assertEqual(result["traces"][5]["response_payload_hex"], "5902FFC0010028")
        self.assertEqual(result["traces"][6]["request_payload_hex"], "14FFFFFF")
        self.assertEqual(result["traces"][7]["response_payload_hex"], "5902FF")
        self.assertEqual(persisted["artifact_type"], "dtc-lifecycle-lab")
        self.assertIn("not a production DEM", markdown)

    def test_reports_expected_state_mismatch_as_finding(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["experiments"][0]["steps"][1]["expected_status"] = 0x2D
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dtc_lifecycle(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["code"], "DTC-LIFECYCLE-MISMATCH")


if __name__ == "__main__":
    unittest.main()
