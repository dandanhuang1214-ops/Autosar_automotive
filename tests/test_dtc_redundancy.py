from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_aging import _CycleState
from automotive_workbench.dtc_redundancy import _Copy, _select_copy, run_dtc_redundancy_lab


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcRedundancyTests(unittest.TestCase):
    def test_selects_matching_copies_without_finding(self) -> None:
        copies = {
            "A": _Copy.from_state(_CycleState(status=0x2F, state="confirmed"), 3),
            "B": _Copy.from_state(_CycleState(status=0x2F, state="confirmed"), 3),
        }

        selected, finding, message = _select_copy(copies)

        self.assertEqual(selected, "A")
        self.assertEqual(finding, "")
        self.assertEqual(message, "Redundant copies agree")

    def test_select_rejects_equal_generation_divergence(self) -> None:
        copies = {
            "A": _Copy.from_state(_CycleState(status=0, state="absent"), 3),
            "B": _Copy.from_state(_CycleState(status=0x2F, state="confirmed"), 3),
        }

        selected, finding, _ = _select_copy(copies)

        self.assertEqual(selected, "")
        self.assertEqual(finding, "DTC-REDUNDANCY-ARBITRATION-FAILED")

    def test_select_reports_restore_failure_when_both_copies_are_invalid(self) -> None:
        copies = {
            "A": _Copy.from_state(_CycleState(status=0, state="absent"), 1),
            "B": _Copy.from_state(_CycleState(status=0x2F, state="confirmed"), 2),
        }
        copies["A"].checksum = "0" * 64
        copies["B"].checksum = "0" * 64

        selected, finding, message = _select_copy(copies)

        self.assertEqual(selected, "")
        self.assertEqual(finding, "DTC-REDUNDANCY-RESTORE-FAILED")
        self.assertEqual(message, "No valid redundant copy is available")

    def test_runs_generation_selection_and_corrupt_newest_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_redundancy_lab(INTENT, output)
            persisted = json.loads(
                (output / "dtc-redundancy-report.json").read_text(encoding="utf-8")
            )
            markdown = (output / "dtc-redundancy-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 13)
        self.assertEqual(result["expected_fault_count"], 3)
        self.assertEqual(result["finding_count"], 3)
        self.assertEqual(result["traces"][5]["selected_copy"], "A")
        self.assertEqual(result["traces"][5]["runtime_status_hex"], "0x2F")
        self.assertEqual(result["traces"][12]["selected_copy"], "B")
        self.assertEqual(result["traces"][12]["runtime_status_hex"], "0x00")
        self.assertEqual(persisted["artifact_type"], "dtc-redundancy-lab")
        self.assertIn("Generation ordering", markdown)

    def test_reports_mismatched_expected_selection(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["redundancy_experiments"][0]["steps"][-1]["expected_selected_copy"] = "B"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")

            result = run_dtc_redundancy_lab(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed_count"], 12)


if __name__ == "__main__":
    unittest.main()
