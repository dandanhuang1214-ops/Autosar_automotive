from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.adapters.dbc import validate_dbc_intent
from automotive_workbench.can_runtime import run_can_lab
from automotive_workbench.communication_evidence import (
    bind_communication_evidence,
    run_communication_chain,
)


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class CommunicationEvidenceTests(unittest.TestCase):
    @staticmethod
    def _write_report(path: Path, report: dict[str, object]) -> Path:
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_binds_both_static_paths_to_tx_and_rx_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "communication"
            result = run_communication_chain(DBC, INTENT, output)
            persisted = json.loads(
                (output / "communication-evidence-report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual((result["bound_count"], result["path_count"]), (2, 2))
        self.assertEqual(result["finding_count"], 0)
        bindings = {item["identity"]: item for item in result["bindings"]}
        self.assertEqual(bindings["WindowStatus.WindowPosition"]["runtime_observation"]["direction"], "tx")
        self.assertEqual(bindings["WindowCommand.RequestedDirection"]["runtime_observation"]["direction"], "rx")
        self.assertEqual(persisted["schema_version"], "communication-evidence-0.1")

    def test_fails_closed_when_runtime_identity_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = run_can_lab(DBC, root / "runtime")
            static = validate_dbc_intent(DBC, INTENT)
            changed = copy.deepcopy(runtime)
            changed["scenarios"][1]["evidence"]["message_name"] = "UnknownCommand"
            report_path = self._write_report(root / "changed-runtime.json", changed)

            result = bind_communication_evidence(static, report_path, DBC, INTENT)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["bound_count"], 1)
        self.assertIn(
            "COMMUNICATION-RUNTIME-EVIDENCE-MISSING",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_runtime_frame_and_direction_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = run_can_lab(DBC, root / "runtime")
            static = validate_dbc_intent(DBC, INTENT)
            changed = copy.deepcopy(runtime)
            changed["scenarios"][0]["evidence"]["frame_id"] = 0x101
            changed["scenarios"][0]["evidence"]["direction"] = "rx"
            report_path = self._write_report(root / "changed-runtime.json", changed)

            result = bind_communication_evidence(static, report_path, DBC, INTENT)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(result["status"], "failed")
        self.assertIn("COMMUNICATION-FRAME-ID-MISMATCH", codes)
        self.assertIn("COMMUNICATION-DIRECTION-MISMATCH", codes)

    def test_static_validation_failure_prevents_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = json.loads(INTENT.read_text(encoding="utf-8"))
            payload["messages"][0]["canif_pdu"] = "WrongPdu"
            changed_intent = root / "intent.json"
            changed_intent.write_text(json.dumps(payload), encoding="utf-8")
            static = validate_dbc_intent(DBC, changed_intent)
            run_can_lab(DBC, root / "runtime")

            result = bind_communication_evidence(
                static,
                root / "runtime" / "can-runtime-report.json",
                DBC,
                changed_intent,
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "COMMUNICATION-STATIC-VALIDATION-FAILED",
            {finding["code"] for finding in result["findings"]},
        )


if __name__ == "__main__":
    unittest.main()
