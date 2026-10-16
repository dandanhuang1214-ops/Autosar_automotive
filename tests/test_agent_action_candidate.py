from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_action_candidate import (
    ACTION_CANDIDATE_BOUNDARY,
    CANDIDATE_SELECTION_BOUNDARY,
    CANDIDATE_SELECT_TOOL,
    CandidateSelectionRunner,
    build_approval_request_from_candidate_selection,
    issue_action_candidate,
    load_and_verify_action_candidate,
    load_and_verify_candidate_selection,
    save_action_candidate,
    save_candidate_selection,
    verify_action_candidate,
    verify_approval_request_from_candidate_selection,
    verify_candidate_selection,
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


class NativeCandidateClient:
    capabilities = ModelCapabilities(False, True, False, True, True)
    url = "fixture://candidate"
    records: list[dict] = []

    def __init__(self, name: str, arguments: dict, *, identity: str = "a") -> None:
        self.name = name
        self.arguments = arguments
        self.identity_value = identity
        self.requests: list[dict] = []

    def service_version(self):
        return "fixture-approval-1"

    def identity(self, name):
        return {"name": name, "digest": self.identity_value * 64, "details": {}}

    def complete(self, payload):
        raise AssertionError("candidate runner must use a bounded interface")

    def usage(self, response):
        return {}

    def complete_structured(self, **kwargs):
        raise AssertionError("native candidate client must use tool calling")

    def complete_tool_call(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return ToolCompletion(
            name=self.name,
            arguments=copy.deepcopy(self.arguments),
            content="",
            input_tokens=24,
            output_tokens=4,
            raw={},
        )


class StructuredCandidateClient(NativeCandidateClient):
    capabilities = ModelCapabilities(True, False, False, True, True)

    def __init__(self, selection: dict, *, identity: str = "a") -> None:
        super().__init__("", {}, identity=identity)
        self.selection = selection

    def complete_tool_call(self, **kwargs):
        raise AssertionError("structured candidate client must not call tools")

    def complete_structured(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return StructuredCompletion(
            content=canonical(self.selection),
            input_tokens=24,
            output_tokens=4,
            raw={},
        )


class UnavailableCandidateClient(NativeCandidateClient):
    def complete_tool_call(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        raise OSError("fixture candidate service unavailable")


class AgentActionCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checkpoint = approval_checkpoint()
        self.evidence_id = self.checkpoint["events"][-1]["observation_id"]
        self.candidate = issue_action_candidate(
            self.checkpoint,
            tool_name=VIRTUAL_CAN_TOOL,
            arguments={"frame_id": 0x456, "payload_hex": "BEEF"},
            evidence_ids=[self.evidence_id],
        )

    def test_control_plane_issues_exact_schema_valid_candidate(self) -> None:
        verified = verify_action_candidate(self.checkpoint, self.candidate)
        self.assertEqual(verified["action"], self.candidate["action"])
        self.assertEqual(self.candidate["boundary"], ACTION_CANDIDATE_BOUNDARY)
        self.assertFalse(self.candidate["execution_authorized"])
        self.assertFalse(self.candidate["tool_invoked"])
        schema = json.loads(
            (ROOT / "schemas/agent-action-candidate.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(self.candidate)

        with self.assertRaisesRegex(ValueError, "Invalid virtual CAN"):
            issue_action_candidate(
                self.checkpoint,
                tool_name=VIRTUAL_CAN_TOOL,
                arguments={
                    "frame_id": 0x456,
                    "payload_hex": "BEEF",
                    "channel": "can0",
                },
                evidence_ids=[self.evidence_id],
            )

    def test_native_model_can_only_select_id_and_action_is_copied_exactly(self) -> None:
        client = NativeCandidateClient(
            CANDIDATE_SELECT_TOOL,
            {"candidate_id": self.candidate["candidate_id"]},
        )
        selection = CandidateSelectionRunner(client).run(
            self.checkpoint, [self.candidate]
        )
        verified = verify_candidate_selection(
            self.checkpoint, [self.candidate], selection
        )
        self.assertEqual(selection["status"], "approval_required")
        self.assertEqual(selection["requested_action"], self.candidate["action"])
        self.assertEqual(verified["requested_action"], self.candidate["action"])
        self.assertEqual(selection["boundary"], CANDIDATE_SELECTION_BOUNDARY)
        self.assertFalse(selection["execution_authorized"])
        self.assertFalse(selection["tool_invoked"])

        tools = client.requests[0]["tools"]
        select_schema = tools[0]["function"]["parameters"]
        self.assertEqual(select_schema["required"], ["candidate_id"])
        self.assertEqual(
            set(select_schema["properties"]), {"candidate_id"}
        )
        self.assertNotIn("frame_id", canonical(tools))
        self.assertNotIn("payload_hex", canonical(tools))

        schema = json.loads(
            (
                ROOT
                / "schemas/agent-action-candidate-selection.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(selection)

    def test_extra_model_arguments_and_unknown_ids_fail_closed(self) -> None:
        extra = CandidateSelectionRunner(
            NativeCandidateClient(
                CANDIDATE_SELECT_TOOL,
                {
                    "candidate_id": self.candidate["candidate_id"],
                    "frame_id": 1,
                },
            )
        ).run(self.checkpoint, [self.candidate])
        self.assertEqual(extra["status"], "refused")
        self.assertIsNone(extra["requested_action"])
        verify_candidate_selection(self.checkpoint, [self.candidate], extra)

        changed_reason = copy.deepcopy(extra)
        changed_reason["reason"] = "different refusal"
        changed_reason["selection_id"] = digest(
            {
                key: changed_reason[key]
                for key in changed_reason
                if key != "selection_id"
            }
        )
        with self.assertRaisesRegex(ValueError, "recorded response"):
            verify_candidate_selection(
                self.checkpoint, [self.candidate], changed_reason
            )

        unknown = CandidateSelectionRunner(
            NativeCandidateClient(
                CANDIDATE_SELECT_TOOL, {"candidate_id": "f" * 64}
            )
        ).run(self.checkpoint, [self.candidate])
        self.assertEqual(unknown["status"], "refused")
        self.assertIsNone(unknown["requested_action"])
        verify_candidate_selection(self.checkpoint, [self.candidate], unknown)

    def test_unavailable_model_attempt_remains_offline_verifiable(self) -> None:
        selection = CandidateSelectionRunner(
            UnavailableCandidateClient(
                CANDIDATE_SELECT_TOOL,
                {"candidate_id": self.candidate["candidate_id"]},
            )
        ).run(self.checkpoint, [self.candidate])
        self.assertEqual(selection["status"], "blocked")
        self.assertEqual(selection["usage"]["model_calls"], 1)
        self.assertIsNone(selection["model_response"])
        self.assertEqual(
            verify_candidate_selection(
                self.checkpoint, [self.candidate], selection
            )["selection_status"],
            "blocked",
        )

    def test_decline_and_structured_selection_are_verifiable(self) -> None:
        declined = CandidateSelectionRunner(
            NativeCandidateClient(
                "agent_decline", {"reason": "action_not_required"}
            )
        ).run(self.checkpoint, [self.candidate])
        self.assertEqual(declined["status"], "declined")
        self.assertIsNone(declined["requested_action"])
        verify_candidate_selection(self.checkpoint, [self.candidate], declined)

        structured = CandidateSelectionRunner(
            StructuredCandidateClient(
                {
                    "action": "select",
                    "candidate_id": self.candidate["candidate_id"],
                    "reason": "",
                }
            )
        ).run(self.checkpoint, [self.candidate])
        self.assertEqual(structured["status"], "approval_required")
        self.assertIsNone(structured["model_response"]["tool_call"])
        verify_candidate_selection(self.checkpoint, [self.candidate], structured)

    def test_candidate_and_selection_tampering_breaks_binding(self) -> None:
        selection = CandidateSelectionRunner(
            NativeCandidateClient(
                CANDIDATE_SELECT_TOOL,
                {"candidate_id": self.candidate["candidate_id"]},
            )
        ).run(self.checkpoint, [self.candidate])

        changed_candidate = copy.deepcopy(self.candidate)
        changed_candidate["action"]["arguments"]["frame_id"] = 1
        with self.assertRaises(ValueError):
            verify_candidate_selection(
                self.checkpoint, [changed_candidate], selection
            )

        changed_selection = copy.deepcopy(selection)
        changed_selection["requested_action"]["arguments"]["frame_id"] = 1
        changed_selection["selection_id"] = digest(
            {
                key: changed_selection[key]
                for key in changed_selection
                if key != "selection_id"
            }
        )
        with self.assertRaisesRegex(ValueError, "Invalid selected"):
            verify_candidate_selection(
                self.checkpoint, [self.candidate], changed_selection
            )

    def test_approval_request_preserves_sealed_action_and_files_replay(self) -> None:
        selection = CandidateSelectionRunner(
            NativeCandidateClient(
                CANDIDATE_SELECT_TOOL,
                {"candidate_id": self.candidate["candidate_id"]},
            )
        ).run(self.checkpoint, [self.candidate])
        created = datetime(2026, 10, 16, tzinfo=timezone.utc)
        request = build_approval_request_from_candidate_selection(
            self.checkpoint,
            [self.candidate],
            selection,
            reason="核对控制面签发的精确虚拟 CAN 动作。",
            created_at=created,
            expires_at=created + timedelta(minutes=15),
        )
        self.assertEqual(request["requested_action"], self.candidate["action"])
        self.assertEqual(request["evidence_ids"], self.candidate["evidence_ids"])
        self.assertFalse(request["execution_authorized"])
        linked = verify_approval_request_from_candidate_selection(
            self.checkpoint, [self.candidate], selection, request
        )
        self.assertEqual(linked["request_id"], request["request_id"])
        self.assertEqual(linked["candidate_id"], self.candidate["candidate_id"])

        different_candidate = issue_action_candidate(
            self.checkpoint,
            tool_name=VIRTUAL_CAN_TOOL,
            arguments={"frame_id": 0x123, "payload_hex": "00"},
            evidence_ids=[self.evidence_id],
        )
        with self.assertRaisesRegex(ValueError, "differs from selected"):
            verify_approval_request_from_candidate_selection(
                self.checkpoint,
                [different_candidate],
                CandidateSelectionRunner(
                    NativeCandidateClient(
                        CANDIDATE_SELECT_TOOL,
                        {"candidate_id": different_candidate["candidate_id"]},
                    )
                ).run(self.checkpoint, [different_candidate]),
                request,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_path = root / "checkpoint.json"
            candidate_path = root / "candidate.json"
            selection_path = root / "selection.json"
            checkpoint_path.write_text(
                canonical(self.checkpoint) + "\n", encoding="utf-8"
            )
            save_action_candidate(
                self.checkpoint, self.candidate, candidate_path
            )
            save_candidate_selection(
                self.checkpoint,
                [self.candidate],
                selection,
                selection_path,
            )
            self.assertEqual(
                load_and_verify_action_candidate(
                    checkpoint_path, candidate_path
                )["status"],
                "passed",
            )
            self.assertEqual(
                load_and_verify_candidate_selection(
                    checkpoint_path, [candidate_path], selection_path
                )["selection_status"],
                "approval_required",
            )

    def test_identity_drift_refuses_before_model_call(self) -> None:
        client = NativeCandidateClient(
            CANDIDATE_SELECT_TOOL,
            {"candidate_id": self.candidate["candidate_id"]},
            identity="b",
        )
        selection = CandidateSelectionRunner(client).run(
            self.checkpoint, [self.candidate]
        )
        self.assertEqual(selection["status"], "refused")
        self.assertEqual(selection["reason"], "model_identity_changed")
        self.assertEqual(selection["usage"]["model_calls"], 0)
        self.assertEqual(client.requests, [])
        verify_candidate_selection(self.checkpoint, [self.candidate], selection)

    def test_success_cannot_claim_an_exhausted_wall_clock_budget(self) -> None:
        selection = CandidateSelectionRunner(
            NativeCandidateClient(
                CANDIDATE_SELECT_TOOL,
                {"candidate_id": self.candidate["candidate_id"]},
            )
        ).run(self.checkpoint, [self.candidate])
        changed = copy.deepcopy(selection)
        changed["usage"]["elapsed_ms"] = (
            self.checkpoint["budget"]["max_seconds"] * 1000 + 1
        )
        changed["selection_id"] = digest(
            {key: changed[key] for key in changed if key != "selection_id"}
        )
        with self.assertRaisesRegex(ValueError, "model evidence"):
            verify_candidate_selection(self.checkpoint, [self.candidate], changed)


if __name__ == "__main__":
    unittest.main()
