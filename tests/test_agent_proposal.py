from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_proposal import (
    ACTION_PROPOSAL_BOUNDARY,
    ActionProposalRunner,
    build_approval_request_from_proposal,
    build_restricted_action_catalog,
    load_and_verify_action_proposal,
    save_action_proposal,
    verify_action_proposal,
)
from automotive_workbench.agent_virtual_execution import VIRTUAL_CAN_TOOL
from automotive_workbench.model_client import (
    ModelCapabilities,
    StructuredCompletion,
    ToolCompletion,
)
from automotive_workbench.project_explanation import canonical, digest
from tests.test_agent_approval import approval_checkpoint


ROOT = Path(__file__).resolve().parents[1]


class StructuredProposalClient:
    capabilities = ModelCapabilities(True, False, False, True, True)
    url = "fixture://proposal"
    records: list[dict] = []

    def __init__(
        self,
        selection,
        *,
        identity="a",
        input_tokens=30,
        output_tokens=8,
    ) -> None:
        self.selection = selection
        self.identity_value = identity
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.requests = []

    def service_version(self):
        return "fixture-approval-1"

    def identity(self, name):
        return {"name": name, "digest": self.identity_value * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("proposal runner must use structured boundary")

    def usage(self, response):
        return {}

    def complete_structured(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return StructuredCompletion(
            content=canonical(self.selection),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            raw={"selection": self.selection},
        )


class NativeProposalClient(StructuredProposalClient):
    capabilities = ModelCapabilities(False, True, False, True, True)

    def complete_structured(self, **kwargs):
        raise AssertionError("native proposal must not use structured output")

    def complete_tool_call(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return ToolCompletion(
            name=self.selection["tool_name"],
            arguments=copy.deepcopy(self.selection["arguments"]),
            content="",
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            raw={"selection": self.selection},
        )


def proposed_action() -> dict:
    return {
        "action": "propose",
        "tool_name": VIRTUAL_CAN_TOOL,
        "arguments": {"frame_id": 0x321, "payload_hex": "102A"},
        "reason": "",
    }


class AgentProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checkpoint = approval_checkpoint()

    def test_structured_model_proposes_but_cannot_invoke(self) -> None:
        client = StructuredProposalClient(proposed_action())
        proposal = ActionProposalRunner(client).run(self.checkpoint)
        verified = verify_action_proposal(self.checkpoint, proposal)
        self.assertEqual(proposal["status"], "approval_required")
        self.assertEqual(proposal["requested_action"]["tool_name"], VIRTUAL_CAN_TOOL)
        self.assertEqual(verified["proposal_status"], "approval_required")
        self.assertFalse(proposal["execution_authorized"])
        self.assertFalse(proposal["tool_invoked"])
        self.assertEqual(proposal["boundary"], ACTION_PROPOSAL_BOUNDARY)
        self.assertNotIn("handler", build_restricted_action_catalog().manifest()[0])
        schema = json.loads(
            (ROOT / "schemas/agent-action-proposal.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(proposal)

    def test_native_selection_is_a_proposal_not_a_tool_call(self) -> None:
        client = NativeProposalClient(proposed_action())
        proposal = ActionProposalRunner(client).run(self.checkpoint)
        self.assertEqual(proposal["status"], "approval_required")
        self.assertEqual(proposal["model_interface"], "native_tool_call")
        names = [item["function"]["name"] for item in client.requests[0]["tools"]]
        self.assertEqual(names, [VIRTUAL_CAN_TOOL, "agent_decline"])
        self.assertEqual(
            proposal["model_response"]["tool_call"],
            {
                "name": VIRTUAL_CAN_TOOL,
                "arguments": proposed_action()["arguments"],
            },
        )
        self.assertEqual(
            proposal["model_response_sha256"], digest(proposal["model_response"])
        )
        self.assertFalse(proposal["tool_invoked"])

        changed = copy.deepcopy(proposal)
        changed["model_response"]["tool_call"] = {
            "name": "agent_decline",
            "arguments": {"reason": "action_not_required"},
        }
        changed["model_response_sha256"] = digest(changed["model_response"])
        changed["proposal_id"] = digest(
            {key: changed[key] for key in changed if key != "proposal_id"}
        )
        with self.assertRaisesRegex(
            ValueError, "Invalid Agent proposed action"
        ):
            verify_action_proposal(self.checkpoint, changed)

    def test_decline_and_invalid_arguments_do_not_create_actions(self) -> None:
        declined = ActionProposalRunner(
            StructuredProposalClient(
                {
                    "action": "decline",
                    "tool_name": "",
                    "arguments": {},
                    "reason": "action_not_required",
                }
            )
        ).run(self.checkpoint)
        self.assertEqual(declined["status"], "declined")
        self.assertIsNone(declined["requested_action"])
        self.assertEqual(
            verify_action_proposal(self.checkpoint, declined)["proposal_status"],
            "declined",
        )

        invalid = proposed_action()
        invalid["arguments"]["channel"] = "vcan0"
        refused = ActionProposalRunner(StructuredProposalClient(invalid)).run(
            self.checkpoint
        )
        self.assertEqual(refused["status"], "refused")
        self.assertIsNone(refused["requested_action"])
        self.assertFalse(refused["tool_invoked"])
        verify_action_proposal(self.checkpoint, refused)

        native_invalid = proposed_action()
        native_invalid["arguments"]["channel"] = "can0"
        native_refused = ActionProposalRunner(
            NativeProposalClient(native_invalid)
        ).run(self.checkpoint)
        self.assertEqual(native_refused["status"], "refused")
        self.assertEqual(
            native_refused["model_response"]["tool_call"]["arguments"][
                "channel"
            ],
            "can0",
        )
        self.assertIsNone(native_refused["model_selection"])
        verify_action_proposal(self.checkpoint, native_refused)

        changed_response = copy.deepcopy(native_refused)
        changed_response["model_response"]["tool_call"]["arguments"][
            "channel"
        ] = "vcan0"
        with self.assertRaisesRegex(
            ValueError, "Invalid Agent action proposal response"
        ):
            verify_action_proposal(self.checkpoint, changed_response)

    def test_legacy_proposal_remains_verifiable(self) -> None:
        current = ActionProposalRunner(
            StructuredProposalClient(proposed_action())
        ).run(self.checkpoint)
        legacy = copy.deepcopy(current)
        legacy["schema_version"] = "agent-action-proposal-0.1"
        response = legacy.pop("model_response")
        legacy["model_response_content"] = response["content"]
        legacy["model_response_sha256"] = "a" * 64
        legacy["proposal_id"] = digest(
            {key: legacy[key] for key in legacy if key != "proposal_id"}
        )
        self.assertEqual(
            verify_action_proposal(self.checkpoint, legacy)["proposal_status"],
            "approval_required",
        )

    def test_identity_drift_fails_before_model_call(self) -> None:
        client = StructuredProposalClient(proposed_action(), identity="b")
        proposal = ActionProposalRunner(client).run(self.checkpoint)
        self.assertEqual(proposal["status"], "refused")
        self.assertEqual(proposal["reason"], "model_identity_changed")
        self.assertEqual(proposal["usage"]["model_calls"], 0)
        self.assertEqual(client.requests, [])
        verify_action_proposal(self.checkpoint, proposal)

    def test_post_response_token_refusal_remains_verifiable(self) -> None:
        remaining = (
            self.checkpoint["budget"]["max_total_tokens"]
            - self.checkpoint["usage"]["total_tokens"]
        )
        proposal = ActionProposalRunner(
            StructuredProposalClient(
                proposed_action(), input_tokens=remaining, output_tokens=1
            )
        ).run(self.checkpoint)
        self.assertEqual(proposal["status"], "refused")
        self.assertEqual(proposal["reason"], "token_budget_exhausted")
        self.assertGreater(
            proposal["usage"]["cumulative_total_tokens"],
            self.checkpoint["budget"]["max_total_tokens"],
        )
        verify_action_proposal(self.checkpoint, proposal)

    def test_proposal_converts_to_exact_approval_and_reverifies_offline(self) -> None:
        proposal = ActionProposalRunner(
            StructuredProposalClient(proposed_action())
        ).run(self.checkpoint)
        created = datetime(2026, 10, 15, 2, 0, tzinfo=timezone.utc)
        request = build_approval_request_from_proposal(
            self.checkpoint,
            proposal,
            reason="Operator must review the model-proposed exact frame.",
            created_at=created,
            expires_at=created + timedelta(minutes=15),
        )
        self.assertEqual(request["requested_action"], proposal["requested_action"])
        self.assertFalse(request["execution_authorized"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint_path = root / "checkpoint.json"
            proposal_path = root / "proposal.json"
            checkpoint_path.write_text(
                canonical(self.checkpoint) + "\n", encoding="utf-8"
            )
            save_action_proposal(self.checkpoint, proposal, proposal_path)
            verified = load_and_verify_action_proposal(
                checkpoint_path, proposal_path
            )
        self.assertEqual(verified["requested_action"], request["requested_action"])

        changed = copy.deepcopy(proposal)
        changed["tool_invoked"] = True
        with self.assertRaisesRegex(ValueError, "Invalid Agent action proposal"):
            verify_action_proposal(self.checkpoint, changed)


if __name__ == "__main__":
    unittest.main()
