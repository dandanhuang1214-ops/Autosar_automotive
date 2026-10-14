from __future__ import annotations

import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_approval import (
    build_agent_approval_decision,
    build_agent_approval_request,
)
from automotive_workbench.agent_transaction import (
    TRANSACTION_BOUNDARY,
    build_agent_approval_claim,
    claim_agent_approval,
    complete_agent_transaction,
    load_and_verify_agent_transaction,
    transaction_paths,
    verify_agent_approval_claim,
    verify_agent_transaction_receipt,
)
from automotive_workbench.project_explanation import canonical
from tests.test_agent_approval import approval_checkpoint


ROOT = Path(__file__).resolve().parents[1]


class AgentTransactionTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = approval_checkpoint()
        self.evidence_id = self.checkpoint["events"][-1]["observation_id"]
        self.created = datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)
        self.expires = self.created + timedelta(minutes=15)
        self.request = build_agent_approval_request(
            self.checkpoint,
            tool_name="configuration.write",
            permission="write",
            arguments={"object": "ComSignal/WindowPosition", "value": 42},
            reason="Operator must review the exact object and value.",
            evidence_ids=[self.evidence_id],
            created_at=self.created,
            expires_at=self.expires,
        )
        self.decision = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="operator-a",
            reason="Approved for a non-executing transaction rehearsal.",
        )

    def test_claim_is_deterministic_idempotent_and_never_authorizes(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"
            first = claim_agent_approval(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                claimed_at=self.created + timedelta(minutes=2),
            )
            retry = claim_agent_approval(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                claimed_at=self.created + timedelta(minutes=3),
            )
            self.assertEqual(retry, first)
            self.assertFalse(first["execution_authorized"])
            self.assertFalse(first["side_effect_performed"])
            self.assertEqual(first["boundary"], TRANSACTION_BOUNDARY)
            claim_path, receipt_path = transaction_paths(
                ledger, self.checkpoint, self.request
            )
            self.assertTrue(claim_path.is_file())
            self.assertFalse(receipt_path.exists())
            self.assertEqual(
                verify_agent_approval_claim(
                    self.checkpoint, self.request, self.decision, first
                )["transaction_state"],
                "claimed",
            )

    def test_concurrent_claims_converge_on_one_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"

            def claim():
                return claim_agent_approval(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    claimed_at=self.created + timedelta(minutes=2),
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                claims = list(executor.map(lambda _: claim(), range(16)))
            self.assertEqual({item["claim_id"] for item in claims}, {claims[0]["claim_id"]})
            claim_path, _ = transaction_paths(ledger, self.checkpoint, self.request)
            self.assertEqual(len(list(claim_path.parent.iterdir())), 1)

    def test_competing_decision_stale_and_denied_claims_fail_closed(self):
        competing = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="operator-b",
            reason="A distinct decision branch.",
        )
        denied = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="denied",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="operator-a",
            reason="Denied.",
        )
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"
            claim_agent_approval(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                claimed_at=self.created + timedelta(minutes=2),
            )
            with self.assertRaisesRegex(ValueError, "bound decision"):
                claim_agent_approval(
                    self.checkpoint,
                    self.request,
                    competing,
                    ledger,
                    claimed_at=self.created + timedelta(minutes=2),
                )
        with self.assertRaisesRegex(ValueError, "Only an approved"):
            build_agent_approval_claim(
                self.checkpoint,
                self.request,
                denied,
                claimed_at=self.created + timedelta(minutes=2),
            )
        with self.assertRaisesRegex(ValueError, "stale"):
            build_agent_approval_claim(
                self.checkpoint,
                self.request,
                self.decision,
                claimed_at=self.expires,
            )

    def test_claim_recovery_and_terminal_receipt_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger"
            claim = claim_agent_approval(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                claimed_at=self.created + timedelta(minutes=2),
            )
            receipt = complete_agent_transaction(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                status="simulated",
                reason="No side effect was invoked.",
                completed_at=self.created + timedelta(minutes=3),
            )
            receipt_schema = json.loads(
                (
                    ROOT
                    / "schemas/readonly-agent-transaction-receipt.schema.json"
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator(
                receipt_schema, format_checker=FormatChecker()
            ).validate(receipt)
            retry = complete_agent_transaction(
                self.checkpoint,
                self.request,
                self.decision,
                ledger,
                status="simulated",
                reason="No side effect was invoked.",
                completed_at=self.created + timedelta(minutes=4),
            )
            self.assertEqual(retry, receipt)
            self.assertFalse(receipt["side_effect_performed"])
            self.assertEqual(
                verify_agent_transaction_receipt(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    claim,
                    receipt,
                )["transaction_state"],
                "simulated",
            )
            with self.assertRaisesRegex(ValueError, "another terminal receipt"):
                complete_agent_transaction(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    status="aborted",
                    reason="Conflicting terminal state.",
                    completed_at=self.created + timedelta(minutes=4),
                )

            checkpoint_path = root / "checkpoint.json"
            request_path = root / "request.json"
            decision_path = root / "decision.json"
            for path, artifact in (
                (checkpoint_path, self.checkpoint),
                (request_path, self.request),
                (decision_path, self.decision),
            ):
                path.write_text(canonical(artifact) + "\n", encoding="utf-8")
            self.assertEqual(
                load_and_verify_agent_transaction(
                    checkpoint_path, request_path, decision_path, ledger
                )["transaction_state"],
                "simulated",
            )

    def test_schemas_tampering_and_missing_claim_fail_closed(self):
        claim = build_agent_approval_claim(
            self.checkpoint,
            self.request,
            self.decision,
            claimed_at=self.created + timedelta(minutes=2),
        )
        claim_schema = json.loads(
            (ROOT / "schemas/readonly-agent-approval-claim.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(
            claim_schema, format_checker=FormatChecker()
        ).validate(claim)
        changed = copy.deepcopy(claim)
        changed["side_effect_performed"] = True
        with self.assertRaisesRegex(ValueError, "Invalid Agent approval claim"):
            verify_agent_approval_claim(
                self.checkpoint, self.request, self.decision, changed
            )
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "ledger"
            with self.assertRaisesRegex(ValueError, "claimed before completion"):
                complete_agent_transaction(
                    self.checkpoint,
                    self.request,
                    self.decision,
                    ledger,
                    status="aborted",
                    reason="Nothing was claimed.",
                    completed_at=self.created + timedelta(minutes=2),
                )


if __name__ == "__main__":
    unittest.main()
