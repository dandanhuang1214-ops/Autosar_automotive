from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_approval import (
    APPROVAL_BOUNDARY,
    build_agent_approval_decision,
    build_agent_approval_request,
    load_and_verify_agent_approval,
    save_agent_approval_decision,
    save_agent_approval_request,
    verify_agent_approval_decision,
    verify_agent_approval_request,
)
from automotive_workbench.agent_runtime import AgentRunner, ToolRegistry, ToolSpec
from automotive_workbench.cli import main
from automotive_workbench.model_client import ModelCapabilities, StructuredCompletion
from automotive_workbench.project_explanation import canonical


ROOT = Path(__file__).resolve().parents[1]


class ApprovalClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://approval-model"
    records: list[dict] = []

    def service_version(self):
        return "fixture-approval-1"

    def identity(self, name):
        return {"name": name, "digest": "a" * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("AgentRunner must use structured completion")

    def usage(self, response):
        return {}

    def complete_structured(self, **kwargs):
        action = {
            "action": "tool",
            "tool_name": "project_lookup",
            "arguments": {"question": "status"},
            "summary": "",
            "evidence_ids": [],
        }
        return StructuredCompletion(
            content=canonical(action),
            input_tokens=20,
            output_tokens=5,
            raw={"action": action},
        )


def approval_checkpoint():
    registry = ToolRegistry({"fixture": "approval"})
    registry.register(
        ToolSpec(
            name="project_lookup",
            description="Return one fixture fact.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["question"],
                "properties": {"question": {"type": "string", "minLength": 1}},
            },
            handler=lambda arguments: {
                "schema_version": "fixture-result-0.1",
                "question": arguments["question"],
                "value": "blocked",
            },
        )
    )
    return AgentRunner(ApprovalClient(), registry).run(
        "需要修改配置", "fixture:1", pause_after_tool_calls=1
    )


class AgentApprovalTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = approval_checkpoint()
        self.evidence_id = self.checkpoint["events"][-1]["observation_id"]
        self.created = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)
        self.expires = self.created + timedelta(minutes=15)
        self.request = build_agent_approval_request(
            self.checkpoint,
            tool_name="configuration.write",
            permission="write",
            arguments={"object": "ComSignal/WindowPosition", "value": 42},
            reason="需要操作者确认精确对象和值。",
            evidence_ids=[self.evidence_id],
            created_at=self.created,
            expires_at=self.expires,
        )

    def test_request_and_approval_are_hash_bound_but_never_authorize_execution(self):
        verified = verify_agent_approval_request(self.checkpoint, self.request)
        self.assertEqual(verified["approval_state"], "pending")
        self.assertFalse(verified["execution_authorized"])
        self.assertEqual(self.request["boundary"], APPROVAL_BOUNDARY)

        decision = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="local-operator",
            reason="已核对对象和值，仅记录批准。",
        )
        verified_decision = verify_agent_approval_decision(
            self.checkpoint, self.request, decision
        )
        self.assertEqual(verified_decision["approval_state"], "approved")
        self.assertFalse(verified_decision["execution_authorized"])

        request_schema = json.loads(
            (ROOT / "schemas/readonly-agent-approval-request.schema.json").read_text(
                encoding="utf-8"
            )
        )
        decision_schema = json.loads(
            (ROOT / "schemas/readonly-agent-approval-decision.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(
            request_schema, format_checker=FormatChecker()
        ).validate(self.request)
        Draft202012Validator(
            decision_schema, format_checker=FormatChecker()
        ).validate(decision)

    def test_denial_and_expiry_are_terminal_request_bound_states(self):
        denied = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="denied",
            decided_at=self.created + timedelta(minutes=2),
            actor_id="operator-a",
            reason="风险范围不清楚。",
        )
        self.assertEqual(
            verify_agent_approval_decision(
                self.checkpoint, self.request, denied
            )["approval_state"],
            "denied",
        )
        expired = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="expired",
            decided_at=self.expires,
            reason="request_expired",
        )
        self.assertEqual(expired["actor"]["kind"], "system")
        self.assertEqual(
            verify_agent_approval_decision(
                self.checkpoint, self.request, expired
            )["approval_state"],
            "expired",
        )
        with self.assertRaisesRegex(ValueError, "has expired"):
            build_agent_approval_decision(
                self.checkpoint,
                self.request,
                status="approved",
                decided_at=self.expires,
                actor_id="operator-a",
                reason="too late",
            )
        with self.assertRaisesRegex(ValueError, "expiry transition"):
            build_agent_approval_decision(
                self.checkpoint,
                self.request,
                status="expired",
                decided_at=self.created,
                reason="request_expired",
            )

    def test_model_self_approval_tampering_and_read_tool_requests_fail_closed(self):
        changed = copy.deepcopy(self.request)
        changed["requested_action"]["arguments"]["value"] = 43
        with self.assertRaisesRegex(ValueError, "approval action"):
            verify_agent_approval_request(self.checkpoint, changed)

        with self.assertRaisesRegex(ValueError, "justification"):
            build_agent_approval_request(
                self.checkpoint,
                tool_name="configuration.write",
                permission="write",
                arguments={},
                reason="missing evidence",
                evidence_ids=["f" * 64],
                created_at=self.created,
                expires_at=self.expires,
            )
        with self.assertRaisesRegex(ValueError, "read tools"):
            build_agent_approval_request(
                self.checkpoint,
                tool_name="project_lookup",
                permission="execute",
                arguments={},
                reason="read does not need approval",
                evidence_ids=[self.evidence_id],
                created_at=self.created,
                expires_at=self.expires,
            )

        decision = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="operator-a",
            reason="record only",
        )
        changed_decision = copy.deepcopy(decision)
        changed_decision["actor"] = {"kind": "model", "id": "fixture:1"}
        with self.assertRaisesRegex(ValueError, "operator decision"):
            verify_agent_approval_decision(
                self.checkpoint, self.request, changed_decision
            )

    def test_expiry_window_and_immutable_files_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "within 24 hours"):
            build_agent_approval_request(
                self.checkpoint,
                tool_name="configuration.write",
                permission="write",
                arguments={},
                reason="too long",
                evidence_ids=[self.evidence_id],
                created_at=self.created,
                expires_at=self.created + timedelta(days=2),
            )
        decision = build_agent_approval_decision(
            self.checkpoint,
            self.request,
            status="approved",
            decided_at=self.created + timedelta(minutes=1),
            actor_id="operator-a",
            reason="record only",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint_path = root / "checkpoint.json"
            request_path = root / "request.json"
            decision_path = root / "decision.json"
            checkpoint_path.write_text(
                canonical(self.checkpoint) + "\n", encoding="utf-8"
            )
            save_agent_approval_request(
                self.checkpoint, self.request, request_path
            )
            save_agent_approval_decision(
                self.checkpoint, self.request, decision, decision_path
            )
            self.assertEqual(
                load_and_verify_agent_approval(
                    checkpoint_path, request_path, decision_path
                )["approval_state"],
                "approved",
            )
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_approval_request(
                    self.checkpoint, self.request, request_path
                )
            with self.assertRaisesRegex(ValueError, "absent"):
                save_agent_approval_decision(
                    self.checkpoint, self.request, decision, decision_path
                )

    def test_cli_records_and_offline_verifies_request_and_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint_path = root / "checkpoint.json"
            arguments_path = root / "arguments.json"
            request_path = root / "request.json"
            decision_path = root / "decision.json"
            checkpoint_path.write_text(
                canonical(self.checkpoint) + "\n", encoding="utf-8"
            )
            arguments_path.write_text(
                canonical({"object": "ComSignal/WindowPosition", "value": 42})
                + "\n",
                encoding="utf-8",
            )

            commands = [
                [
                    "workbench",
                    "request-agent-approval",
                    str(checkpoint_path),
                    str(arguments_path),
                    "--tool-name",
                    "configuration.write",
                    "--permission",
                    "write",
                    "--reason",
                    "operator review required",
                    "--evidence-id",
                    self.evidence_id,
                    "--output",
                    str(request_path),
                ],
                [
                    "workbench",
                    "verify-agent-approval-request",
                    str(checkpoint_path),
                    str(request_path),
                ],
                [
                    "workbench",
                    "decide-agent-approval",
                    str(checkpoint_path),
                    str(request_path),
                    "--decision",
                    "approved",
                    "--actor",
                    "local-operator",
                    "--reason",
                    "record only",
                    "--output",
                    str(decision_path),
                ],
                [
                    "workbench",
                    "verify-agent-approval-decision",
                    str(checkpoint_path),
                    str(request_path),
                    str(decision_path),
                ],
            ]
            for command in commands:
                with self.subTest(command=command[1]), redirect_stdout(io.StringIO()):
                    with patch.object(sys, "argv", command):
                        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
