from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_intent import load_dtc_intent, summarize_dtc_intent


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcIntentTests(unittest.TestCase):
    def test_loads_public_dtc_lifecycle_intent(self) -> None:
        payload = load_dtc_intent(INTENT)
        summary = summarize_dtc_intent(INTENT)

        self.assertEqual(payload["schema_version"], "dtc-intent-0.1")
        self.assertEqual(summary["dtcs"][0]["code_hex"], "0xC00100")
        self.assertEqual(summary["experiments"][0]["step_count"], 8)
        self.assertEqual(summary["cycle_experiment_count"], 1)
        self.assertEqual(summary["cycle_experiments"][0]["step_count"], 12)
        self.assertEqual(summary["reset_experiment_count"], 2)
        self.assertEqual(summary["reset_experiments"][0]["step_count"], 8)
        self.assertEqual(summary["reset_experiments"][1]["step_count"], 4)
        self.assertEqual(summary["persistence_fault_experiment_count"], 2)
        self.assertEqual(summary["persistence_fault_experiments"][0]["step_count"], 6)
        self.assertEqual(summary["persistence_fault_experiments"][1]["step_count"], 7)

    def test_rejects_experiment_with_unknown_dtc(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["experiments"][0]["dtc"] = 0xFFFFFF
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtc_intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "references unknown code"):
                load_dtc_intent(path)

    def test_requires_status_mask_for_read_step(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        del payload["experiments"][0]["steps"][5]["status_mask"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtc_intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "status_mask"):
                load_dtc_intent(path)

    def test_rejects_status_bits_outside_availability_mask(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["status_availability_mask"] = 0x0F
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtc_intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "uses unavailable bits"):
                load_dtc_intent(path)

    def test_rejects_unsupported_persistence_policy(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["dtcs"][0]["persistence"]["flush_event"] = "automatic"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtc_intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicit flush_event"):
                load_dtc_intent(path)

    def test_rejects_unsupported_persistence_expected_finding(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["persistence_fault_experiments"][0]["steps"][0]["expected_finding"] = "UNKNOWN"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtc_intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported DTC persistence expected Finding"):
                load_dtc_intent(path)


if __name__ == "__main__":
    unittest.main()
