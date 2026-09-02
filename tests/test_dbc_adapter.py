from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.adapters.dbc import inspect_dbc, validate_dbc_intent


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class DbcAdapterTests(unittest.TestCase):
    def test_inspects_physical_signal_definition(self) -> None:
        result = inspect_dbc(DBC)
        self.assertEqual(result["message_count"], 2)
        position = result["messages"][0]["signals"][0]
        self.assertEqual(position["start_bit"], 0)
        self.assertEqual(position["byte_order"], "little_endian")
        self.assertEqual(position["maximum"], 100)

    def test_public_sample_matches_intent(self) -> None:
        result = validate_dbc_intent(DBC, INTENT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["findings"], [])

    def test_reports_message_and_signal_mismatches(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["messages"][0]["dlc"] = 7
        payload["signals"][0]["start_bit"] = 1
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed_intent.json"
            changed.write_text(json.dumps(payload), encoding="utf-8")
            result = validate_dbc_intent(DBC, changed)
        codes = [finding["code"] for finding in result["findings"]]
        self.assertEqual(result["status"], "failed")
        self.assertIn("DBC-DLC-MISMATCH", codes)
        self.assertIn("DBC-SIGNAL-PROPERTY-MISMATCH", codes)

    def test_reports_cross_level_pdu_reference_mismatch(self) -> None:
        payload = json.loads(INTENT.read_text(encoding="utf-8"))
        payload["messages"][0]["canif_pdu"] = "WindowStatus_CanIfRxPdu"
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed_intent.json"
            changed.write_text(json.dumps(payload), encoding="utf-8")
            result = validate_dbc_intent(DBC, changed)
        findings = [
            finding
            for finding in result["findings"]
            if finding["code"] == "INTENT-CROSS-LEVEL-REFERENCE-MISMATCH"
        ]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["field"], "canif_pdu")
        self.assertEqual(findings[0]["location"], "WindowStatus.WindowPosition")


if __name__ == "__main__":
    unittest.main()
