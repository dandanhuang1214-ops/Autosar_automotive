from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.uds_runtime import probe_uds_backend, run_uds_lab


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
        self.assertEqual(result["passed_count"], 9)
        scenarios = {item["scenario"]: item for item in result["scenarios"]}
        self.assertEqual(scenarios["read_vin"]["evidence"]["decoded_value"], "AWBDEMO0123456789")
        self.assertEqual(scenarios["read_vin"]["evidence"]["response_payload_hex"][:6], "62F190")
        self.assertEqual(scenarios["unknown_did_nrc"]["observed"], "RequestOutOfRange")
        self.assertEqual(scenarios["unknown_did_nrc"]["evidence"]["response_payload_hex"], "7F2231")
        self.assertEqual(scenarios["response_timeout"]["observed"], "timeout")
        malformed = scenarios["malformed_window_position_payload"]
        self.assertEqual(malformed["status"], "passed")
        self.assertEqual(malformed["evidence"]["response_payload_hex"], "62F111")
        self.assertEqual(malformed["evidence"]["findings"][0]["code"], "UDS-MALFORMED-PAYLOAD")
        read_dtc = scenarios["read_healed_obstruction_dtc"]
        self.assertEqual(
            read_dtc["evidence"]["actual_dtc_records"],
            [{"code": 12583168, "code_hex": "0xC00100", "status": 40, "status_hex": "0x28"}],
        )
        self.assertEqual(read_dtc["evidence"]["response_payload_hex"], "5902FFC0010028")
        snapshot = scenarios["read_obstruction_snapshot"]
        self.assertEqual(snapshot["evidence"]["response_payload_hex"], "5904C00100280101F1112A")
        self.assertEqual(
            snapshot["evidence"]["actual_snapshot_records"],
            [{"record_number": 1, "did": 61713, "did_hex": "0xF111", "value": 42, "payload_hex": "2A"}],
        )
        self.assertEqual(scenarios["clear_all_dtcs"]["evidence"]["response_payload_hex"], "54")
        self.assertEqual(scenarios["read_dtcs_after_clear"]["evidence"]["actual_dtc_records"], [])
        self.assertEqual(scenarios["read_dtcs_after_clear"]["evidence"]["response_payload_hex"], "5902FF")
        snapshot_after_clear = scenarios["read_snapshot_after_clear"]
        self.assertEqual(snapshot_after_clear["evidence"]["actual_snapshot_records"], [])
        self.assertEqual(snapshot_after_clear["evidence"]["response_payload_hex"], "5904C0010000")
        self.assertEqual(persisted["transport"]["request_id_hex"], "0x700")
        self.assertEqual(persisted["transport"]["response_id_hex"], "0x708")
        self.assertEqual(persisted["backend_probe"]["status"], "available")
        self.assertEqual(
            persisted["isolation"]["client"]["frame_filters"][0]["can_id_hex"],
            "0x708",
        )
        self.assertEqual(
            persisted["isolation"]["server"]["frame_filters"][0]["can_id_hex"],
            "0x700",
        )
        self.assertEqual(len(persisted["responder_observed_requests"]), 9)
        self.assertIn("not a DCM", markdown)

    def test_blocks_socketcan_uds_lab_when_interface_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            result = run_uds_lab(INTENT, BusConfig("socketcan", "workbench-missing-vcan"), output)
            persisted = json.loads((output / "uds-lab-report.json").read_text(encoding="utf-8"))
            probe = json.loads((output / "probe" / "backend-probe.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "interface_missing")
        self.assertEqual(result["scenario_count"], 9)
        self.assertEqual(result["passed_count"], 0)
        self.assertEqual(persisted["backend_probe"]["status"], "blocked")
        self.assertEqual(probe["reason"], "interface_missing")
        self.assertEqual(
            persisted["isolation"]["client"]["frame_filters"][0]["can_id_hex"],
            "0x708",
        )

    def test_probes_uds_backend_dependencies_and_can_backend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe"
            result = probe_uds_backend(BusConfig("virtual", "workbench-uds-probe"), output)
            persisted = json.loads((output / "uds-backend-probe.json").read_text(encoding="utf-8"))
            markdown = (output / "uds-backend-probe.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["can_backend_probe"]["status"], "available")
        self.assertTrue(result["dependencies"]["python_can"]["present"])
        self.assertTrue(result["dependencies"]["can_isotp"]["present"])
        self.assertTrue(result["dependencies"]["udsoncan"]["present"])
        self.assertEqual(persisted["transport_strategy"], result["transport_strategy"])
        self.assertIn("current lab path uses user-space can-isotp", markdown)

    def test_probes_uds_backend_as_blocked_when_socketcan_interface_is_missing(self) -> None:
        result = probe_uds_backend(BusConfig("socketcan", "workbench-missing-vcan"))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "interface_missing")
        self.assertEqual(result["can_backend_probe"]["reason"], "interface_missing")
        self.assertIn("kernel_isotp", result)


if __name__ == "__main__":
    unittest.main()
