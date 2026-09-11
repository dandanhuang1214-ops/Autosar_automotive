from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from scripts.check_installed_capsule_consumer import run_installed_capsule_consumer


ROOT = Path(__file__).resolve().parents[1]


class InstalledCapsuleConsumerTests(unittest.TestCase):
    def test_installed_wheel_verifies_relocated_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "consumer"
            result = run_installed_capsule_consumer(ROOT, output)
            persisted = json.loads(
                (output / "installed-capsule-consumer.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, persisted)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified_file_count"], 16)
        self.assertEqual(result["verified_artifact_count"], 7)
        self.assertEqual(result["verified_dependency_count"], 3)
        schema = json.loads(
            (ROOT / "schemas" / "installed-capsule-consumer.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validator = validator_for(schema)(schema, format_checker=FormatChecker())
        validator.validate(result)
        invalid = {**result, "verified_file_count": False}
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_rejects_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "consumer"
            output.mkdir()
            (output / "stale.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_installed_capsule_consumer(ROOT, output)

    def test_rejects_symlink_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            output = root / "consumer"
            try:
                output.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks are not available on this platform")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                run_installed_capsule_consumer(ROOT, output)


if __name__ == "__main__":
    unittest.main()
