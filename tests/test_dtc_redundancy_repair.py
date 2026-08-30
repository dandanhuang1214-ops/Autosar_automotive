from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.dtc_aging import _CycleState
from automotive_workbench.dtc_redundancy import _Copy, _select_copy
from automotive_workbench.dtc_redundancy_repair import (
    _RepairContext,
    _repair,
    run_dtc_redundancy_repair_lab,
)


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


class DtcRedundancyRepairTests(unittest.TestCase):
    def test_uncommitted_newer_copy_is_not_selectable(self) -> None:
        copies = {
            "A": _Copy.from_state(
                _CycleState(status=0x2F, state="confirmed"),
                2,
                committed=False,
            ),
            "B": _Copy.from_state(_CycleState(status=0, state="absent"), 1),
        }

        selected, finding, _ = _select_copy(copies)

        self.assertEqual(selected, "B")
        self.assertEqual(finding, "DTC-REDUNDANCY-LOSS")

    def test_repair_refuses_without_selected_committed_source(self) -> None:
        context = _RepairContext(
            runtime=_CycleState(),
            copies={
                "A": _Copy.from_state(_CycleState(), 0, committed=False),
                "B": _Copy.from_state(_CycleState(), 0, committed=False),
            },
        )

        outcome, finding, _ = _repair(context, staged=False)

        self.assertEqual(outcome, "refused")
        self.assertEqual(finding, "DTC-REDUNDANCY-REPAIR-REFUSED")

    def test_runs_interrupted_write_repair_and_interrupted_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_dtc_redundancy_repair_lab(INTENT, output)
            persisted = json.loads(
                (output / "dtc-redundancy-repair-report.json").read_text(
                    encoding="utf-8"
                )
            )
            markdown = (output / "dtc-redundancy-repair-report.md").read_text(
                encoding="utf-8"
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["experiment_count"], 3)
        self.assertEqual(result["passed_count"], 25)
        self.assertEqual(result["expected_fault_count"], 6)
        self.assertEqual(result["finding_count"], 6)
        self.assertEqual(result["traces"][6]["selected_copy"], "B")
        self.assertEqual(result["traces"][13]["repair_outcome"], "committed")
        self.assertEqual(result["traces"][14]["repair_outcome"], "no-op")
        self.assertEqual(result["traces"][15]["actual_finding"], "")
        self.assertFalse(result["traces"][23]["copy_b_committed"])
        self.assertEqual(result["traces"][24]["selected_copy"], "A")
        self.assertEqual(persisted["artifact_type"], "dtc-redundancy-repair-lab")
        self.assertIn("Commit markers", markdown)

    def test_reports_mismatched_expected_repair_outcome(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["redundancy_repair_experiments"][1]["steps"][6][
            "expected_repair_outcome"
        ] = "no-op"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intent = root / "dtc_intent.json"
            intent.write_text(json.dumps(payload), encoding="utf-8")

            result = run_dtc_redundancy_repair_lab(intent, root / "output")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed_count"], 24)


if __name__ == "__main__":
    unittest.main()
