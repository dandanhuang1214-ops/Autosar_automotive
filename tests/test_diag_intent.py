from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.diag_intent import load_uds_intent, summarize_uds_intent


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "uds_intent.json"
DTC_INTENT = ROOT / "examples" / "window_control" / "dtc_intent.json"


def _write_intent(directory: str, payload: dict[str, object]) -> Path:
    root = Path(directory)
    path = root / "uds_intent.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    (root / "dtc_intent.json").write_text(DTC_INTENT.read_text(encoding="utf-8"), encoding="utf-8")
    return path


class UdsIntentTests(unittest.TestCase):
    def test_loads_public_window_control_diagnostic_intent(self) -> None:
        payload = load_uds_intent(INTENT)
        summary = summarize_uds_intent(INTENT)

        self.assertEqual(payload["schema_version"], "uds-intent-0.1")
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["ecu"], "WindowController")
        self.assertEqual(summary["transport"]["request_id_hex"], "0x700")
        self.assertEqual(summary["transport"]["response_id_hex"], "0x708")
        self.assertEqual(summary["did_count"], 2)
        self.assertEqual(summary["dids"][0]["id_hex"], "0xF190")
        self.assertEqual(summary["scenario_count"], 15)
        self.assertEqual(summary["scenarios"][3]["expected"], "malformed_payload")
        self.assertEqual(summary["scenarios"][4]["status_mask_hex"], "0x08")
        self.assertEqual(summary["scenarios"][5]["dtc_hex"], "0xC00100")
        self.assertEqual(summary["scenarios"][6]["dtc_hex"], "0xC00100")
        self.assertEqual(summary["scenarios"][11]["group_hex"], "0xFFFFFF")

    def test_rejects_positive_scenario_with_unknown_did(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["scenarios"][0]["did"] = 0x9999

        with tempfile.TemporaryDirectory() as directory:
            path = _write_intent(directory, payload)
            with self.assertRaisesRegex(ValueError, "Positive UDS scenario references unknown DID"):
                load_uds_intent(path)

    def test_rejects_ambiguous_transport_ids(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["transport"]["response_id"] = payload["transport"]["request_id"]

        with tempfile.TemporaryDirectory() as directory:
            path = _write_intent(directory, payload)
            with self.assertRaisesRegex(ValueError, "request_id and response_id must differ"):
                load_uds_intent(path)

    def test_rejects_malformed_scenario_with_non_hex_payload(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["scenarios"][3]["response_payload_hex"] = "not-hex"

        with tempfile.TemporaryDirectory() as directory:
            path = _write_intent(directory, payload)
            with self.assertRaisesRegex(ValueError, "response_payload_hex must be hexadecimal"):
                load_uds_intent(path)

    def test_rejects_clear_for_unknown_dtc_group(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["scenarios"][11]["group"] = 0x123456

        with tempfile.TemporaryDirectory() as directory:
            path = _write_intent(directory, payload)
            with self.assertRaisesRegex(ValueError, "references unknown group"):
                load_uds_intent(path)

    def test_rejects_positive_extended_data_scenario_with_unknown_record(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["scenarios"][6]["record_number"] = 0x44

        with tempfile.TemporaryDirectory() as directory:
            path = _write_intent(directory, payload)
            with self.assertRaisesRegex(ValueError, "references unknown record"):
                load_uds_intent(path)


if __name__ == "__main__":
    unittest.main()
