from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from scripts.check_installed_distribution import run_installed_distribution_smoke


ROOT = Path(__file__).resolve().parents[1]


class InstalledDistributionTests(unittest.TestCase):
    def test_builds_and_runs_installed_cli_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "distribution-smoke"
            result = run_installed_distribution_smoke(ROOT, output)
            persisted = json.loads(
                (output / "installed-distribution-smoke.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse((output / "wheel").exists())

        self.assertEqual(result, persisted)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["distribution"]["name"], "automotive-workbench")
        self.assertEqual(result["distribution"]["version"], "0.1.0")
        self.assertEqual(len(result["distribution"]["wheel_sha256"]), 64)
        schema = json.loads(
            (ROOT / "schemas" / "installed-distribution-smoke.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validator = validator_for(schema)(schema, format_checker=FormatChecker())
        validator.validate(result)
        incomplete = {**result, "checks": result["checks"][:-1]}
        self.assertTrue(list(validator.iter_errors(incomplete)))

    def test_rejects_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "distribution-smoke"
            output.mkdir()
            (output / "stale.whl").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_installed_distribution_smoke(ROOT, output)


if __name__ == "__main__":
    unittest.main()
