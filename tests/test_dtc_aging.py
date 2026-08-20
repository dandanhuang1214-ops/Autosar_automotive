from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_aging import _CycleState, _apply_cycle_event, run_dtc_aging_lab
from automotive_workbench.dtc_intent import load_dtc_intent


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcAgingTests(unittest.TestCase):
    def test_untested_cycle_does_not_advance_aging(self) -> None:
        definition = load_dtc_intent(INTENT)["dtcs"][0]
        state = _CycleState()
        for event in (
            "operation_cycle_start",
            "fault_present",
            "fault_present",
            "operation_cycle_end",
            "operation_cycle_start",
            "operation_cycle_end",
        ):
            _apply_cycle_event(state, event, definition)

        self.assertEqual(state.state, "confirmed")
        self.assertEqual(state.aging_counter, 0)
        self.assertTrue(state.snapshot)

    def test_runs_operation_cycles_aging_and_snapshot_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_aging_lab(INTENT, output)
            persisted = json.loads((output / "dtc-aging-report.json").read_text(encoding="utf-8"))
            markdown = (output / "dtc-aging-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 12)
        self.assertEqual(result["finding_count"], 0)
        self.assertEqual(result["traces"][3]["request_payload_hex"], "1904C0010001")
        self.assertEqual(result["traces"][3]["response_payload_hex"], "5904C001002F0101F1112A")
        self.assertEqual(result["traces"][7]["observed_aging_counter"], 1)
        self.assertEqual(result["traces"][2]["observed_occurrence_counter"], 1)
        self.assertTrue(result["traces"][7]["extended_data_stored"])
        self.assertEqual(result["traces"][10]["observed_state"], "aged_out")
        self.assertFalse(result["traces"][10]["snapshot_stored"])
        self.assertFalse(result["traces"][10]["extended_data_stored"])
        self.assertEqual(result["traces"][11]["response_payload_hex"], "5904C0010000")
        self.assertEqual(persisted["artifact_type"], "dtc-aging-lab")
        self.assertIn("not a production Dem", markdown)

    def test_reports_monitor_event_outside_cycle(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["cycle_experiments"][0]["steps"][0]["event"] = "fault_present"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")
            result = run_dtc_aging_lab(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["findings"][0]["code"], "DTC-CYCLE-SEQUENCE")
        self.assertIn("requires an active operation cycle", result["findings"][0]["message"])


if __name__ == "__main__":
    unittest.main()
