from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.bsw_intent import load_intent
from automotive_workbench.cli import main
from automotive_workbench.communication_plan import (
    compile_plan,
    load_declaration,
    preflight_communication,
    validate_declaration,
)

ROOT = Path(__file__).resolve().parents[1]


class CommunicationPlanTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "examples/thermal_control"
        self.dbc = self.root / "thermal_control.dbc"
        self.intent_path = self.root / "bsw_intent.json"
        self.declaration_path = self.root / "communication_vectors.json"
        self.database = _load_dbc(self.dbc)
        self.intent = load_intent(self.intent_path)
        self.declaration = load_declaration(self.declaration_path)
        self.validator = Draft202012Validator(
            json.loads(
                (ROOT / "schemas/communication-vectors.schema.json").read_text(
                    encoding="utf-8"
                )
            )
        )

    def test_two_structurally_different_plans_and_raw_quantization(self):
        for name, count in [("window_control", 2), ("thermal_control", 3)]:
            root = ROOT / "examples" / name
            result = preflight_communication(
                root / (name + ".dbc"),
                root / "bsw_intent.json",
                root / "communication_vectors.json",
            )
            Draft202012Validator(
                json.loads(
                    (ROOT / "schemas/communication-plan.schema.json").read_text(
                        encoding="utf-8"
                    )
                )
            ).validate(result)
            self.assertEqual(len(result["vectors"]), count)
            self.assertEqual({v["direction"] for v in result["vectors"]}, {"tx", "rx"})
            self.assertEqual(len(result["source_artifacts"]), 3)
        vector = result["vectors"][0]
        self.assertEqual(vector["payload_hex"], "c7044b00")
        self.assertEqual(
            vector["expected_raw_signals"], {"CoolantTemperature": 1223, "FanDuty": 75}
        )
        self.assertNotEqual(
            vector["signals"]["CoolantTemperature"],
            vector["expected_signals"]["CoolantTemperature"],
        )
        self.assertEqual(vector["signals"]["CoolantTemperature"], 82.34)

    def test_schema_loader_shared_constraints(self):
        self.validator.validate(self.declaration)
        bad = [None, [], {}, {"schema_version": [], "vectors": []}]
        for key, values in {
            "id": ["", "a/b", "id\n", True, []],
            "message": ["", "  ", 42],
            "direction": ["send", [], None],
            "timeout_seconds": [0, -1, 5.01, True, "1", None],
            "signals": [{}, [], {"FanDuty": True}, {"FanDuty": "1"}, {" ": 1}],
        }.items():
            for value in values:
                item = copy.deepcopy(self.declaration)
                item["vectors"][0][key] = value
                bad.append(item)
        for vectors in [[], [self.declaration["vectors"][0]] * 257]:
            bad.append(
                {"schema_version": "communication-vectors-0.1", "vectors": vectors}
            )
        item = copy.deepcopy(self.declaration)
        item["vectors"][0]["extra"] = 1
        bad.append(item)
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(self.validator.is_valid(value))
                with self.assertRaises(ValueError):
                    validate_declaration(value)

    def test_semantic_failures_are_pure_and_do_not_mutate_inputs(self):
        variants = []
        for key, value in [
            ("message", "Missing"),
            ("direction", "rx"),
            ("signals", {"Unknown": 1}),
            ("signals", {"CoolantTemperature": 80}),
            ("signals", {"CoolantTemperature": 200, "FanDuty": 50}),
        ]:
            item = copy.deepcopy(self.declaration)
            item["vectors"][0][key] = value
            variants.append(item)
        item = copy.deepcopy(self.declaration)
        item["vectors"][1]["id"] = item["vectors"][0]["id"]
        variants.append(item)
        for number in [float("nan"), float("inf"), -float("inf"), 10**1000]:
            item = copy.deepcopy(self.declaration)
            item["vectors"][0]["signals"]["FanDuty"] = number
            variants.append(item)
        for timeout in [float("nan"), float("inf")]:
            item = copy.deepcopy(self.declaration)
            item["vectors"][0]["timeout_seconds"] = timeout
            variants.append(item)
        before = copy.deepcopy(self.declaration)
        with patch("can.Bus") as bus, patch.object(Path, "write_text") as write:
            for value in variants:
                with (
                    self.subTest(value=str(value)[:200]),
                    self.assertRaises(ValueError),
                ):
                    compile_plan(self.database, self.intent, value)
            bus.assert_not_called()
            write.assert_not_called()
        self.assertEqual(self.declaration, before)

    def test_unsupported_dbc_features_and_ambiguous_identities(self):
        for feature in [
            "fd",
            "long",
            "mux",
            "float",
            "duplicate_name",
            "duplicate_frame",
            "receiver",
        ]:
            database = copy.deepcopy(self.database)
            message = database.messages[0]
            if feature == "fd":
                message.is_fd = True
            elif feature == "long":
                message.length = 12
            elif feature == "mux":
                message.signals[0].is_multiplexer = True
            elif feature == "float":
                message.signals[0].is_float = True
            elif feature == "duplicate_name":
                database.messages[1].name = message.name
            elif feature == "duplicate_frame":
                database.messages[1].frame_id = message.frame_id
            elif feature == "receiver":
                database.messages[2].signals[1].receivers.clear()
            with self.subTest(feature=feature), self.assertRaises(ValueError):
                compile_plan(database, self.intent, self.declaration)

    def test_intent_identity_and_direction_conflicts(self):
        for feature in [
            "ecu",
            "frame",
            "dlc",
            "direction",
            "signal_direction",
            "duplicate",
        ]:
            intent = copy.deepcopy(self.intent)
            if feature == "ecu":
                intent["local_ecu"] = ""
            elif feature == "frame":
                intent["messages"][0]["can_id"] += 1
            elif feature == "dlc":
                intent["messages"][0]["dlc"] += 1
            elif feature == "direction":
                intent["messages"][0]["direction"] = "rx"
            elif feature == "signal_direction":
                intent["signals"][0]["direction"] = "rx"
            elif feature == "duplicate":
                intent["messages"].append(intent["messages"][0])
            with self.subTest(feature=feature), self.assertRaises(ValueError):
                compile_plan(self.database, intent, self.declaration)

    def test_cli_read_only_success_and_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "vectors.json"
            path.write_text(json.dumps(self.declaration), encoding="utf-8")
            for valid in [True, False]:
                if not valid:
                    value = copy.deepcopy(self.declaration)
                    value["vectors"][0]["signals"] = {"Unknown": 1}
                    path.write_text(json.dumps(value), encoding="utf-8")
                before = path.read_bytes()
                with (
                    patch(
                        "sys.argv",
                        [
                            "workbench",
                            "plan-communication",
                            str(self.dbc),
                            str(self.intent_path),
                            str(path),
                        ],
                    ),
                    patch("can.Bus") as bus,
                    patch.object(Path, "write_text") as write,
                    redirect_stdout(io.StringIO()) as stream,
                ):
                    code = main()
                self.assertEqual(code, 0 if valid else 1)
                json.loads(stream.getvalue())
                bus.assert_not_called()
                write.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_duplicate_json_keys_rejected_and_bom_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "declaration.json"
            path.write_text(
                '{"schema_version":"communication-vectors-0.1","vectors":[],"vectors":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate JSON member"):
                load_declaration(path)
            path.write_bytes(b"\xef\xbb\xbf" + self.declaration_path.read_bytes())
            self.assertEqual(load_declaration(path), self.declaration)

    def test_mapping_failure_precedes_compilation(self):
        with (
            patch(
                "automotive_workbench.communication_plan.validate_dbc_intent",
                return_value={"status": "failed"},
            ),
            patch(
                "automotive_workbench.communication_plan.compile_plan"
            ) as compile_mock,
        ):
            with self.assertRaisesRegex(ValueError, "valid DBC/intent mapping"):
                preflight_communication(
                    self.dbc, self.intent_path, self.declaration_path
                )
            compile_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
