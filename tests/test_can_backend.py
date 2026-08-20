from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_backend import (
    _contamination_findings,
    probe_can_backend,
    run_backend_lab,
    unique_virtual_config,
)
from automotive_workbench.can_io import BusConfig


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"


def _has_vcan0() -> bool:
    try:
        return any(name == "vcan0" for _, name in socket.if_nameindex())
    except OSError:
        return False


class CanBackendTests(unittest.TestCase):
    def test_contamination_events_become_structured_finding(self) -> None:
        findings = _contamination_findings(
            BusConfig("socketcan", "vcan0"),
            ["timeout phase received unexpected frame 0x708"],
        )

        self.assertEqual(findings[0]["code"], "CAN-CHANNEL-CONTAMINATION")
        self.assertEqual(findings[0]["kind"], "can-channel")
        self.assertEqual(findings[0]["source_artifact"], "vcan0")
        self.assertIn("0x708", findings[0]["message"])

    def test_virtual_backend_probe_and_lab_pass(self) -> None:
        config = unique_virtual_config()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            probe = probe_can_backend(config, output / "probe-only")
            result = run_backend_lab(DBC, config, output / "lab")
            persisted = json.loads(
                (output / "lab" / "backend-lab-report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(probe["status"], "available")
        self.assertTrue(all(probe["capabilities"].values()))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["captured_count"], 3)
        self.assertTrue(result["replay_integrity"])
        self.assertTrue(result["capture_integrity"])
        self.assertEqual(result["contamination_finding_count"], 0)
        self.assertEqual(
            [item["can_id_hex"] for item in result["isolation"]["frame_filters"]],
            ["0x100", "0x101"],
        )
        faults = {item["scenario"]: item for item in result["fault_scenarios"]}
        self.assertEqual(faults["wrong_arbitration_id"]["evidence"]["actual_frame_id"], 0x101)
        self.assertEqual(faults["receive_timeout"]["status"], "passed")
        self.assertEqual(persisted["probe"]["config"]["interface"], "virtual")
        self.assertEqual(persisted["fault_scenarios"][0]["status"], "passed")
        self.assertEqual(persisted["isolation"]["channel_lock"]["status"], "not_managed")

    @unittest.skipUnless(sys.platform == "linux" and _has_vcan0(), "vcan0 unavailable")
    def test_socketcan_backend_uses_same_contract_when_vcan0_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_backend_lab(
                DBC,
                BusConfig("socketcan", "vcan0"),
                Path(directory),
        )
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["replay_integrity"])
        self.assertTrue(all(item["status"] == "passed" for item in result["fault_scenarios"]))

    @unittest.skipIf(sys.platform == "linux", "non-Linux behavior only")
    def test_socketcan_is_structurally_blocked_on_non_linux(self) -> None:
        result = probe_can_backend(BusConfig("socketcan", "vcan0"))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "unsupported_platform")
        self.assertFalse(any(result["capabilities"].values()))


if __name__ == "__main__":
    unittest.main()
