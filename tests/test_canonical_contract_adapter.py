from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.adapters.canonical_contract import _range, validate_contract_mapping


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "window_control"
DBC = SAMPLE / "window_control.dbc"
CONTRACT = SAMPLE / "canonical_contract.json"
INTENT = SAMPLE / "bsw_intent.json"


class CanonicalContractAdapterTests(unittest.TestCase):
    def test_parses_supported_range_notations_without_treating_separator_as_sign(self) -> None:
        self.assertEqual(_range("0-100"), (0.0, 100.0))
        self.assertEqual(_range("-40..125"), (-40.0, 125.0))
        self.assertEqual(_range("[0, 3]"), (0.0, 3.0))

    def test_public_contract_matches_dbc(self) -> None:
        result = validate_contract_mapping(DBC, CONTRACT, INTENT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["checked_count"], 2)
        self.assertTrue(result["not_inferred"])

    def test_reports_scale_unit_and_range_mismatches(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        signal = payload["signals"][0]
        signal["resolution"] = "0.5"
        signal["unit"] = "mm"
        signal["physical_range"] = "0-200"
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "contract.json"
            changed.write_text(json.dumps(payload), encoding="utf-8")
            result = validate_contract_mapping(DBC, changed, INTENT)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(result["status"], "failed")
        self.assertEqual(codes, {"MAP-NUMERIC-MISMATCH", "MAP-UNIT-MISMATCH", "MAP-RANGE-MISMATCH"})


if __name__ == "__main__":
    unittest.main()
