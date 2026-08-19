from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.experiment import run_suite


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "window_control"


class ExperimentSuiteTests(unittest.TestCase):
    def test_runs_baseline_and_fault_injection_suite_and_writes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_suite(
                SAMPLE / "window_control.dbc",
                SAMPLE / "canonical_contract.json",
                SAMPLE / "bsw_intent.json",
                output,
            )
            json_report = output / "experiment-report.json"
            markdown_report = output / "experiment-report.md"
            persisted = json.loads(json_report.read_text(encoding="utf-8"))
            markdown = markdown_report.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["scenario_count"], 6)
        self.assertEqual(result["passed_count"], 6)
        self.assertEqual(persisted["run_id"], result["run_id"])
        self.assertIn("intent_start_bit_mismatch", markdown)
        self.assertIn("does not prove vendor ECUC", markdown)
        sources = {
            finding["source_artifact"]
            for scenario in result["scenarios"]
            for finding in scenario["findings"]
        }
        self.assertFalse(any("Temp" in source or "tmp" in source for source in sources))
        self.assertIn("scenario-input://contract_unit_mismatch/contract", sources)


if __name__ == "__main__":
    unittest.main()
