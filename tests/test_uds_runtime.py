from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.uds_runtime import run_uds_lab


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "uds_intent.json"


class UdsRuntimeTests(unittest.TestCase):
    def test_runs_virtual_uds_positive_nrc_and_timeout_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_uds_lab(INTENT, BusConfig("virtual", "workbench"), output)
            persisted = json.loads((output / "uds-lab-report.json").read_text(encoding="utf-8"))
            markdown = (output / "uds-lab-report.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 3)
        scenarios = {item["scenario"]: item for item in result["scenarios"]}
        self.assertEqual(scenarios["read_vin"]["evidence"]["decoded_value"], "AWBDEMO0123456789")
        self.assertEqual(scenarios["read_vin"]["evidence"]["response_payload_hex"][:6], "62F190")
        self.assertEqual(scenarios["unknown_did_nrc"]["observed"], "RequestOutOfRange")
        self.assertEqual(scenarios["unknown_did_nrc"]["evidence"]["response_payload_hex"], "7F2231")
        self.assertEqual(scenarios["response_timeout"]["observed"], "timeout")
        self.assertEqual(persisted["transport"]["request_id_hex"], "0x700")
        self.assertEqual(persisted["transport"]["response_id_hex"], "0x708")
        self.assertEqual(persisted["backend_probe"]["status"], "available")
        self.assertEqual(len(persisted["responder_observed_requests"]), 3)
        self.assertIn("not a DCM", markdown)

    def test_blocks_socketcan_uds_lab_when_interface_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_uds_lab(INTENT, BusConfig("socketcan", "workbench-missing-vcan"), output)
            persisted = json.loads((output / "uds-lab-report.json").read_text(encoding="utf-8"))
            probe = json.loads((output / "probe" / "backend-probe.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "interface_missing")
        self.assertEqual(result["scenario_count"], 3)
        self.assertEqual(result["passed_count"], 0)
        self.assertEqual(persisted["backend_probe"]["status"], "blocked")
        self.assertEqual(probe["reason"], "interface_missing")


if __name__ == "__main__":
    unittest.main()
