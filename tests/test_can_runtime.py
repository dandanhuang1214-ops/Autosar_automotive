from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_runtime import run_can_lab


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"


class VirtualCanRuntimeTests(unittest.TestCase):
    def test_runs_virtual_bus_and_fault_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_can_lab(DBC, output)
            persisted = json.loads(
                (output / "can-runtime-report.json").read_text(encoding="utf-8")
            )
            markdown = (output / "can-runtime-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 4)
        scenarios = {item["scenario"]: item for item in result["scenarios"]}
        self.assertEqual(scenarios["round_trip"]["evidence"]["payload_hex"], "2A01020000000000")
        self.assertEqual(scenarios["round_trip"]["evidence"]["decoded"]["WindowPosition"], 42)
        self.assertEqual(scenarios["wrong_can_id"]["evidence"]["actual_frame_id"], 0x101)
        self.assertEqual(persisted["backend"], "python-can virtual")
        self.assertIn("does not emulate CAN arbitration", markdown)


if __name__ == "__main__":
    unittest.main()
