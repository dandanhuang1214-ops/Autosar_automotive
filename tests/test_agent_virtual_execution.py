from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_approval import (
    build_agent_approval_decision,
    build_agent_approval_request,
)
from automotive_workbench.agent_transaction import (
    claim_agent_approval,
    load_and_verify_agent_transaction,
)
from automotive_workbench.agent_virtual_execution import (
    VIRTUAL_CAN_TOOL,
    _run_virtual_can_action,
    execute_agent_virtual_can,
    load_and_verify_virtual_execution,
    virtual_execution_paths,
    verify_virtual_execution_receipt,
)
from automotive_workbench.project_explanation import canonical, read
from tests.test_agent_approval import approval_checkpoint


ROOT = Path(__file__).resolve().parents[1]


class AgentVirtualExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checkpoint = approval_checkpoint()
        self.created = datetime(2026, 10, 14, 5, 0, tzinfo=timezone.utc)
        self.request = build_agent_approval_request(
            self.checkpoint,
            tool_name=VIRTUAL_CAN_TOOL,
            permission="execute",
            arguments={"frame_id": 0x321, "payload_hex": "102A"},
            reason="Review one bounded virtual CAN emission.",
            evidence_ids=[self.checkpoint["events"][-1]["observation_id"]],
            created_at=self.created,
            expires_at=self.created + timedelta(minutes=15),
        )
        self.decision = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="local-operator",
            reason="Approved as a local review record; explicit execution remains separate.",
        )

    def claim(self, ledger: Path) -> dict:
        return claim_agent_approval(
            self.checkpoint,
            self.request,
            self.decision,
            ledger,
            claimed_at=self.created + timedelta(minutes=2),
        )

    def test_default_disabled_then_executes_observes_and_compensates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger"
            claim = self.claim(ledger)
            with self.assertRaisesRegex(ValueError, "explicit enable"):
                execute_agent_virtual_can(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    enabled=False,
                    started_at=self.created + timedelta(minutes=3),
                )
            attempt_path, receipt_path = virtual_execution_paths(
                ledger, self.checkpoint, self.request
            )
            self.assertFalse(attempt_path.exists())
            self.assertFalse(receipt_path.exists())

            receipt = execute_agent_virtual_can(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                enabled=True,
                started_at=self.created + timedelta(minutes=3),
                completed_at=self.created + timedelta(minutes=4),
            )
            attempt = read(attempt_path)
            self.assertEqual(receipt["status"], "succeeded")
            self.assertEqual(receipt["idempotency_key"], claim["transaction_id"])
            self.assertEqual(receipt["command_result"]["status"], "returned")
            self.assertEqual(receipt["effect_verification"]["status"], "passed")
            self.assertEqual(receipt["compensation"]["status"], "passed")
            self.assertFalse(receipt["compensation"]["literal_undo"])
            self.assertEqual(receipt["side_effect_status"], "performed")
            self.assertTrue(receipt["virtual_channel"].startswith("workbench-agent-"))
            self.assertFalse(receipt["hardware_accessed"])
            self.assertFalse(receipt["configuration_written"])
            self.assertFalse(receipt["authenticated_authorization"])

            for name, artifact in (
                ("agent-virtual-execution-attempt", attempt),
                ("agent-virtual-execution-receipt", receipt),
            ):
                schema = json.loads(
                    (ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8")
                )
                Draft202012Validator(
                    schema, format_checker=FormatChecker()
                ).validate(artifact)

    def test_completed_retry_is_idempotent_and_does_not_send_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"
            self.claim(ledger)
            first = execute_agent_virtual_can(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                enabled=True,
                started_at=self.created + timedelta(minutes=3),
                completed_at=self.created + timedelta(minutes=4),
            )
            with patch(
                "automotive_workbench.agent_virtual_execution._run_virtual_can_action",
                side_effect=AssertionError("must not execute twice"),
            ):
                retry = execute_agent_virtual_can(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    enabled=True,
                    started_at=self.created + timedelta(minutes=5),
                )
            self.assertEqual(retry, first)

    def test_observation_error_does_not_relabel_successful_send(self) -> None:
        class FakeBus:
            def __init__(self, *, receive_error: bool = False) -> None:
                self.receive_error = receive_error

            def send(self, message, timeout=None) -> None:
                return None

            def recv(self, timeout=None):
                if self.receive_error:
                    raise RuntimeError("synthetic observer failure")
                return None

            def shutdown(self) -> None:
                return None

        receiver = FakeBus(receive_error=True)
        sender = FakeBus()
        cleanup_observer = FakeBus()
        with patch(
            "automotive_workbench.agent_virtual_execution.open_bus",
            side_effect=[receiver, sender, cleanup_observer],
        ):
            command, effect, compensation, side_effect_status = _run_virtual_can_action(
                "a" * 64, {"frame_id": 0x321, "payload_hex": "102A"}
            )
        self.assertEqual(command["status"], "returned")
        self.assertEqual(effect["status"], "failed")
        self.assertEqual(effect["error_type"], "RuntimeError")
        self.assertEqual(side_effect_status, "performed")
        self.assertEqual(compensation["status"], "passed")

    def test_crash_after_attempt_blocks_automatic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"
            self.claim(ledger)
            with patch(
                "automotive_workbench.agent_virtual_execution._run_virtual_can_action",
                side_effect=KeyboardInterrupt,
            ), self.assertRaises(KeyboardInterrupt):
                execute_agent_virtual_can(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    enabled=True,
                    started_at=self.created + timedelta(minutes=3),
                )
            attempt_path, receipt_path = virtual_execution_paths(
                ledger, self.checkpoint, self.request
            )
            self.assertTrue(attempt_path.is_file())
            self.assertFalse(receipt_path.exists())
            with self.assertRaisesRegex(ValueError, "indeterminate"):
                execute_agent_virtual_can(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    enabled=True,
                    started_at=self.created + timedelta(minutes=4),
                )

    def test_exact_tool_arguments_and_tampering_fail_closed(self) -> None:
        wrong = copy.deepcopy(self.request)
        wrong["requested_action"]["arguments"]["channel"] = "vcan0"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "arguments"):
                execute_agent_virtual_can(
                    self.checkpoint,
                    wrong,
                    self.decision,
                    Path(temporary) / "ledger",
                    enabled=True,
                    started_at=self.created,
                )

            ledger = Path(temporary) / "valid-ledger"
            claim = self.claim(ledger)
            receipt = execute_agent_virtual_can(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                enabled=True,
                started_at=self.created + timedelta(minutes=3),
            )
            attempt_path, _ = virtual_execution_paths(
                ledger, self.checkpoint, self.request
            )
            changed = copy.deepcopy(receipt)
            changed["hardware_accessed"] = True
            with self.assertRaisesRegex(ValueError, "Invalid"):
                verify_virtual_execution_receipt(
                    self.request, claim, read(attempt_path), changed
                )

    def test_offline_verifier_uses_only_ledger_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger"
            self.claim(ledger)
            execute_agent_virtual_can(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                enabled=True,
                started_at=self.created + timedelta(minutes=3),
            )
            paths = []
            for name, artifact in (
                ("checkpoint.json", self.checkpoint),
                ("request.json", self.request),
                ("decision.json", self.decision),
            ):
                path = root / name
                path.write_text(canonical(artifact) + "\n", encoding="utf-8")
                paths.append(path)
            verified = load_and_verify_virtual_execution(*paths, ledger)
            self.assertEqual(verified["transaction_state"], "succeeded")
            self.assertEqual(verified["effect_status"], "passed")
            self.assertEqual(verified["compensation_status"], "passed")
            general = load_and_verify_agent_transaction(*paths, ledger)
            self.assertEqual(general, verified)


if __name__ == "__main__":
    unittest.main()
