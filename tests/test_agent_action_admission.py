from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.agent_action_admission import (
    admit_action_candidates,
    build_approval_request_from_admission,
    issue_action_intent,
    load_and_verify_action_admission,
    load_and_verify_action_intent,
    save_action_admission,
    save_action_intent,
    verify_action_admission,
    verify_action_intent,
    verify_approval_request_from_admission,
)
from automotive_workbench.agent_action_candidate import issue_action_candidate
from automotive_workbench.agent_runtime import AgentRunner, ToolRegistry, ToolSpec
from automotive_workbench.agent_virtual_execution import VIRTUAL_CAN_TOOL
from automotive_workbench.project_explanation import canonical, digest
from tests.test_agent_approval import ApprovalClient


ROOT = Path(__file__).resolve().parents[1]


class ActionAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        registry = ToolRegistry({"fixture": "action-admission"})
        registry.register(
            ToolSpec(
                name="project_lookup",
                description="Return one fixture project fact.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question"],
                    "properties": {"question": {"type": "string", "minLength": 1}},
                },
                handler=lambda arguments: {
                    "schema_version": "agent-tool-project-facts-0.1",
                    "question": arguments["question"],
                    "facts": [
                        {
                            "fact_id": "f" * 64,
                            "pointer": "/checks/communication/reason",
                            "value": "structural_gap",
                        }
                    ],
                },
            )
        )
        self.checkpoint = AgentRunner(ApprovalClient(), registry).run(
            "需要核对动作", "fixture:1", pause_after_tool_calls=1
        )
        tool_event = next(
            event for event in self.checkpoint["events"] if event["kind"] == "tool"
        )
        self.observation_id = tool_event["observation_id"]
        self.fact_id = tool_event["result"]["facts"][0]["fact_id"]
        self.actual_value = tool_event["result"]["facts"][0]["value"]
        self.exact = issue_action_candidate(
            self.checkpoint,
            tool_name=VIRTUAL_CAN_TOOL,
            arguments={"frame_id": 0x456, "payload_hex": "BEEF"},
            evidence_ids=[self.observation_id],
        )
        self.decoy = issue_action_candidate(
            self.checkpoint,
            tool_name=VIRTUAL_CAN_TOOL,
            arguments={"frame_id": 1, "payload_hex": "BEEF"},
            evidence_ids=[self.observation_id],
        )

    def exact_spec(self, expected_value: object | None = None) -> dict[str, object]:
        return {
            "disposition": "exact_action",
            "requested_capability": {
                "scope": "process_local_virtual",
                "interface": "virtual",
                "channel": None,
            },
            "requested_action": {
                "tool_name": VIRTUAL_CAN_TOOL,
                "arguments": {"frame_id": 0x456, "payload_hex": "BEEF"},
            },
            "evidence_conditions": [
                {
                    "observation_id": self.observation_id,
                    "selector": {"kind": "fact_id", "value": self.fact_id},
                    "expected_value": (
                        self.actual_value if expected_value is None else expected_value
                    ),
                }
            ],
            "deterministic_decline_reason": None,
        }

    def test_exact_intent_filters_decoy_and_binds_approval(self) -> None:
        intent = issue_action_intent(self.checkpoint, self.exact_spec())
        admission = admit_action_candidates(
            self.checkpoint, intent, [self.decoy, self.exact]
        )
        self.assertEqual(admission["status"], "approval_required")
        self.assertEqual(admission["eligible_candidate_ids"], [self.exact["candidate_id"]])
        self.assertEqual(admission["selected_candidate_id"], self.exact["candidate_id"])
        self.assertEqual(admission["requested_action"], self.exact["action"])
        self.assertFalse(admission["model_invoked"])
        self.assertFalse(admission["execution_authorized"])
        self.assertFalse(admission["tool_invoked"])
        verify_action_intent(self.checkpoint, intent)
        verify_action_admission(
            self.checkpoint, intent, [self.decoy, self.exact], admission
        )

        created = datetime(2026, 10, 16, tzinfo=timezone.utc)
        request = build_approval_request_from_admission(
            self.checkpoint,
            intent,
            [self.decoy, self.exact],
            admission,
            reason="Review the deterministically admitted exact action.",
            created_at=created,
            expires_at=created + timedelta(minutes=15),
        )
        self.assertEqual(request["requested_action"], self.exact["action"])
        linked = verify_approval_request_from_admission(
            self.checkpoint, intent, [self.decoy, self.exact], admission, request
        )
        self.assertEqual(linked["candidate_id"], self.exact["candidate_id"])
        self.assertFalse(linked["model_invoked"])

    def test_fact_mismatch_is_deterministic_decline(self) -> None:
        intent = issue_action_intent(
            self.checkpoint, self.exact_spec(expected_value="not-the-recorded-value")
        )
        admission = admit_action_candidates(
            self.checkpoint, intent, [self.decoy, self.exact]
        )
        self.assertEqual(admission["status"], "declined")
        self.assertEqual(
            admission["reason"], "control_plane_declined:insufficient_evidence"
        )
        self.assertEqual(admission["eligible_candidate_ids"], [])
        self.assertIsNone(admission["requested_action"])
        self.assertFalse(admission["evaluated_conditions"][0]["matched"])
        with self.assertRaisesRegex(ValueError, "Only an admitted"):
            build_approval_request_from_admission(
                self.checkpoint,
                intent,
                [self.decoy, self.exact],
                admission,
                reason="Must not become approval.",
                created_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
                expires_at=datetime(2026, 10, 16, 0, 15, tzinfo=timezone.utc),
            )

    def test_no_action_and_unsupported_capability_bypass_model(self) -> None:
        no_action = issue_action_intent(
            self.checkpoint,
            {
                "disposition": "no_action",
                "requested_capability": None,
                "requested_action": None,
                "evidence_conditions": [],
                "deterministic_decline_reason": "action_not_required",
            },
        )
        no_action_admission = admit_action_candidates(
            self.checkpoint, no_action, [self.exact]
        )
        self.assertEqual(
            no_action_admission["reason"],
            "control_plane_declined:action_not_required",
        )
        unsupported = issue_action_intent(
            self.checkpoint,
            {
                "disposition": "unsupported_action",
                "requested_capability": {
                    "scope": "host_socketcan",
                    "interface": "socketcan",
                    "channel": "can0",
                },
                "requested_action": None,
                "evidence_conditions": [],
                "deterministic_decline_reason": "outside_restricted_capabilities",
            },
        )
        unsupported_admission = admit_action_candidates(
            self.checkpoint, unsupported, [self.exact]
        )
        self.assertEqual(
            unsupported_admission["reason"],
            "control_plane_declined:outside_restricted_capabilities",
        )
        self.assertFalse(no_action_admission["model_invoked"])
        self.assertFalse(unsupported_admission["model_invoked"])

    def test_tamper_schema_and_file_replay(self) -> None:
        intent = issue_action_intent(self.checkpoint, self.exact_spec())
        admission = admit_action_candidates(
            self.checkpoint, intent, [self.decoy, self.exact]
        )
        changed = copy.deepcopy(admission)
        changed["selected_candidate_id"] = self.decoy["candidate_id"]
        changed["admission_id"] = digest(
            {key: changed[key] for key in changed if key != "admission_id"}
        )
        with self.assertRaisesRegex(ValueError, "deterministic result"):
            verify_action_admission(
                self.checkpoint, intent, [self.decoy, self.exact], changed
            )
        malformed_intent = copy.deepcopy(intent)
        malformed_intent["requested_action"] = "not-an-action"
        with self.assertRaisesRegex(ValueError, "Invalid Agent action intent"):
            verify_action_intent(self.checkpoint, malformed_intent)
        unsupported = {
            "disposition": "unsupported_action",
            "requested_capability": {
                "scope": "host_socketcan",
                "interface": "hardware",
                "channel": "can0",
            },
            "requested_action": None,
            "evidence_conditions": [],
            "deterministic_decline_reason": "outside_restricted_capabilities",
        }
        with self.assertRaisesRegex(ValueError, "Invalid Agent action intent capability"):
            issue_action_intent(self.checkpoint, unsupported)

        for name, value in (
            ("agent-action-intent.schema.json", intent),
            ("agent-action-admission.schema.json", admission),
        ):
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).validate(value)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_path = root / "checkpoint.json"
            intent_path = root / "intent.json"
            admission_path = root / "admission.json"
            candidate_paths = [root / "decoy.json", root / "exact.json"]
            checkpoint_path.write_text(
                canonical(self.checkpoint) + "\n", encoding="utf-8"
            )
            for path, candidate in zip(
                candidate_paths, [self.decoy, self.exact], strict=True
            ):
                path.write_text(canonical(candidate) + "\n", encoding="utf-8")
            save_action_intent(self.checkpoint, intent, intent_path)
            save_action_admission(
                self.checkpoint,
                intent,
                [self.decoy, self.exact],
                admission,
                admission_path,
            )
            self.assertEqual(
                load_and_verify_action_intent(checkpoint_path, intent_path)["status"],
                "passed",
            )
            self.assertEqual(
                load_and_verify_action_admission(
                    checkpoint_path, intent_path, candidate_paths, admission_path
                )["admission_status"],
                "approval_required",
            )


if __name__ == "__main__":
    unittest.main()
