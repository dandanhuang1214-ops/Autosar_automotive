from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.communication_delivery import run_communication_delivery


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class CommunicationDeliveryTests(unittest.TestCase):
    def test_delivers_passed_chain_manifest_verification_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "delivery"
            result = run_communication_delivery(DBC, INTENT, output, base=ROOT)
            persisted = json.loads(
                (output / "communication-evidence-delivery.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest_bytes = (output / "manifest.json").read_bytes()
            verification_bytes = (
                output / "verification" / "evidence-bundle-verification.json"
            ).read_bytes()

        self.assertEqual(result, persisted)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["chain_status"], "passed")
        self.assertEqual(result["integrity_status"], "passed")
        self.assertEqual(
            (result["verified_artifact_count"], result["artifact_count"]), (7, 7)
        )
        self.assertEqual(
            (result["verified_dependency_count"], result["dependency_count"]),
            (3, 3),
        )
        self.assertEqual(
            result["manifest_sha256"], hashlib.sha256(manifest_bytes).hexdigest()
        )
        self.assertEqual(
            result["verification_sha256"],
            hashlib.sha256(verification_bytes).hexdigest(),
        )

    def test_preserves_blocked_outcome_with_verified_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "delivery"
            result = run_communication_delivery(
                DBC,
                INTENT,
                output,
                BusConfig("socketcan", "workbench-definitely-missing"),
                base=ROOT,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["chain_status"], "blocked")
        self.assertEqual(result["integrity_status"], "passed")
        self.assertIn(result["reason"], {"interface_missing", "unsupported_platform"})
        self.assertEqual(
            result["verified_artifact_count"], result["artifact_count"]
        )

    def test_preserves_failed_chain_with_verified_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            changed = json.loads(INTENT.read_text(encoding="utf-8"))
            changed["messages"][0]["canif_pdu"] = "WrongPdu"
            intent = root / "invalid-intent.json"
            intent.write_text(json.dumps(changed), encoding="utf-8")
            result = run_communication_delivery(
                DBC, intent, root / "delivery", base=ROOT
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["chain_status"], "failed")
        self.assertEqual(result["integrity_status"], "passed")
        self.assertEqual(
            result["verified_artifact_count"], result["artifact_count"]
        )

    def test_rejects_nonempty_output_to_avoid_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "delivery"
            output.mkdir()
            (output / "existing.txt").write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_communication_delivery(DBC, INTENT, output, base=ROOT)
            self.assertEqual(
                (output / "existing.txt").read_text(encoding="utf-8"), "keep\n"
            )


if __name__ == "__main__":
    unittest.main()
