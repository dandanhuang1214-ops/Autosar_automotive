from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.adapters.generate_arxml import summarize_issue_report


class GenerateArxmlAdapterTests(unittest.TestCase):
    def test_preserves_external_severity_and_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "issues.json"
            path.write_text(json.dumps({
                "mode": "signal",
                "counts": {"open_issues": 1},
                "items": [{
                    "kind": "model_validation",
                    "severity": "ERROR",
                    "code": "MODEL-VALIDATION",
                    "message": "Unknown port",
                    "location": "Ports!R2",
                    "status": "open"
                }]
            }), encoding="utf-8")

            result = summarize_issue_report(path)

        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["by_severity"], {"ERROR": 1})
        self.assertEqual(result["findings"][0]["location"], "Ports!R2")

    def test_rejects_unrecognized_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "other.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing items"):
                summarize_issue_report(path)


if __name__ == "__main__":
    unittest.main()

