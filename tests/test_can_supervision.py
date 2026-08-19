from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_supervision import run_can_supervision


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"


class CanSupervisionTests(unittest.TestCase):
    def test_periodic_timeout_and_recovery_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_can_supervision(DBC, output)
            persisted = json.loads(
                (output / "can-supervision-report.json").read_text(encoding="utf-8")
            )
            markdown = (output / "can-supervision-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 2)
        scenarios = {item["scenario"]: item for item in result["scenarios"]}
        self.assertEqual(scenarios["periodic_baseline"]["evidence"]["received_count"], 6)
        self.assertEqual(
            scenarios["drop_timeout_recovery"]["evidence"]["state_sequence"],
            ["RECEIVING", "TIMEOUT", "RECOVERED"],
        )
        self.assertTrue(scenarios["drop_timeout_recovery"]["evidence"]["recovery_detected"])
        self.assertEqual(persisted["artifact_type"], "can-communication-supervision")
        self.assertIn("not hard real-time behavior", markdown)


if __name__ == "__main__":
    unittest.main()
