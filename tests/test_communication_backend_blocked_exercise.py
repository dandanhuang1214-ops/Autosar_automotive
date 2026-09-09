from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.communication_evidence import run_communication_chain
from scripts.communication_backend_blocked_exercise import check_blocked_evidence


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class CommunicationBackendBlockedExerciseTests(unittest.TestCase):
    def test_accepts_complete_structured_blocked_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            run_communication_chain(
                DBC,
                INTENT,
                output,
                BusConfig("socketcan", "workbench-definitely-missing"),
            )
            result = check_blocked_evidence(output, "failure")
            persisted = json.loads(
                (output / "communication-backend-blocked-exercise.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(persisted["binding_count"], 2)
        self.assertIn(
            persisted["blocked_reason"], {"interface_missing", "unsupported_platform"}
        )

    def test_rejects_successful_cli_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must be failure"):
                check_blocked_evidence(Path(directory), "success")


if __name__ == "__main__":
    unittest.main()
