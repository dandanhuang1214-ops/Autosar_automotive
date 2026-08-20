from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_reset import run_dtc_reset_lab


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcResetTests(unittest.TestCase):
    def test_runs_flush_reset_clear_and_second_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_reset_lab(INTENT, output)
            persisted = json.loads((output / "dtc-reset-report.json").read_text(encoding="utf-8"))
            markdown = (output / "dtc-reset-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 12)
        self.assertEqual(result["traces"][2]["runtime_status_hex"], "0x2F")
        self.assertEqual(result["traces"][2]["persistent_status_hex"], "0x00")
        self.assertEqual(result["traces"][4]["persistent_status_hex"], "0x2F")
        self.assertEqual(result["traces"][5]["request_payload_hex"], "1101")
        self.assertEqual(result["traces"][5]["response_payload_hex"], "5101")
        self.assertTrue(result["traces"][5]["runtime_snapshot_stored"])
        self.assertEqual(result["traces"][7]["runtime_status_hex"], "0x00")
        self.assertFalse(result["traces"][7]["runtime_extended_data_stored"])
        self.assertEqual(result["traces"][10]["runtime_status_hex"], "0x2F")
        self.assertEqual(result["traces"][10]["persistent_status_hex"], "0x00")
        self.assertEqual(result["traces"][11]["runtime_status_hex"], "0x00")
        self.assertFalse(result["traces"][11]["runtime_snapshot_stored"])
        self.assertEqual(persisted["artifact_type"], "dtc-reset-persistence-lab")
        self.assertIn("not AUTOSAR NvM", markdown)

    def test_rejects_flush_during_active_cycle(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["reset_experiments"][0]["steps"][1]["event"] = "flush"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dtc_reset_lab(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["findings"][0]["code"], "DTC-RESET-SEQUENCE")
        self.assertIn("inactive operation cycle", result["findings"][0]["message"])


if __name__ == "__main__":
    unittest.main()
