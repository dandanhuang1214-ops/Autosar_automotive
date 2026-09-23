from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import can
from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.can_io import BusConfig, open_bus
from automotive_workbench.cli import main
from automotive_workbench.communication_plan import preflight_communication
from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.declared_communication import (
    exchange_vector,
    run_declared_communication,
    vector_filter,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = "automotive_workbench.declared_communication"


class DeclaredCommunicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "output"
        self.root = ROOT / "examples/thermal_control"
        self.dbc = self.root / "thermal_control.dbc"
        self.intent = self.root / "bsw_intent.json"
        self.declaration = self.root / "communication_vectors.json"
        self.config = default_communication_config()
        self.plan = preflight_communication(self.dbc, self.intent, self.declaration)
        self.database = _load_dbc(self.dbc)
        self.validator = Draft202012Validator(
            json.loads(
                (ROOT / "schemas/declared-communication-runtime.schema.json").read_text(
                    encoding="utf-8"
                )
            ),
            format_checker=FormatChecker(),
        )

    def run_report(self, declaration=None, config=None, output=None):
        report = run_declared_communication(
            self.dbc,
            self.intent,
            declaration or self.declaration,
            config or self.config,
            output or self.output,
        )
        self.validator.validate(report)
        self.assertEqual(
            report,
            json.loads(
                ((output or self.output) / "declared-runtime-report.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        return report

    def test_two_projects_exchange_every_vector_with_correct_roles(self):
        for name, count in [("thermal_control", 3), ("window_control", 2)]:
            root = ROOT / "examples" / name
            report = run_declared_communication(
                root / (name + ".dbc"),
                root / "bsw_intent.json",
                root / "communication_vectors.json",
                self.config,
                self.output / name,
            )
            self.validator.validate(report)
            self.assertEqual(
                (report["status"], report["passed_count"]), ("passed", count)
            )
            for expected in report["plan"]["vectors"]:
                actual = report["vectors"][expected["id"]]
                self.assertEqual(
                    actual["observed"]["raw_signals"], expected["expected_raw_signals"]
                )
                self.assertEqual(
                    actual["observed"]["payload_hex"], expected["payload_hex"]
                )
                self.assertEqual(
                    actual["sender"],
                    "local" if expected["direction"] == "tx" else "peer",
                )
                self.assertEqual(len(actual["cleanup"]), 2)
                self.assertTrue(all(x["status"] == "passed" for x in actual["cleanup"]))
        self.assertEqual(
            self.plan["vectors"][0]["signals"]["CoolantTemperature"], 82.34
        )
        self.assertEqual(
            self.plan["vectors"][0]["expected_raw_signals"]["CoolantTemperature"], 1223
        )

    def test_repeated_rx_vectors_cannot_consume_previous_traffic(self):
        values = json.loads(self.declaration.read_text(encoding="utf-8"))
        vector = values["vectors"][-1]
        values["vectors"] = []
        for index in range(3):
            item = copy.deepcopy(vector)
            item["id"] = f"rx-{index}"
            item["signals"]["TargetTemperature"] += index
            values["vectors"].append(item)
        path = Path(self.temp.name) / "repeated.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        report = self.run_report(path)
        self.assertEqual(report["passed_count"], 3)
        self.assertEqual(
            [
                v["observed"]["signals"]["TargetTemperature"]
                for v in report["vectors"].values()
            ],
            [75, 76, 77],
        )

    def test_actual_virtual_wrong_id_is_filtered_and_suppressed_send_times_out(self):
        for fault in ["wrong_id", "no_send"]:
            opened = []

            def factory(config, filters):
                bus = open_bus(config, filters)
                wrapper = MagicMock(wraps=bus)
                opened.append(wrapper)
                real_send = bus.send

                def send(message, **kwargs):
                    if fault == "wrong_id":
                        message = copy.copy(message)
                        message.arbitration_id += 1
                        real_send(message, **kwargs)

                wrapper.send.side_effect = send
                return wrapper

            vector = copy.deepcopy(self.plan["vectors"][0])
            vector["timeout_seconds"] = 0.01
            with (
                self.subTest(fault=fault),
                patch(MODULE + ".open_bus", side_effect=factory),
            ):
                result = exchange_vector(self.database, vector, self.config)
            self.assertEqual(
                (result["status"], result["reason"]), ("failed", "receive_timeout")
            )
            self.assertIsNone(result["observed"])
            for bus in opened:
                bus.shutdown.assert_called_once()

    def test_observed_faults_have_precise_reasons(self):
        vector = self.plan["vectors"][0]
        baseline = can.Message(
            arbitration_id=vector["frame_id"],
            is_extended_id=False,
            data=bytes.fromhex(vector["payload_hex"]),
        )
        for fault, reason in [
            ("id", "frame_identity_mismatch"),
            ("extended", "frame_identity_mismatch"),
            ("fd", "unsupported_frame"),
            ("remote", "unsupported_frame"),
            ("error", "unsupported_frame"),
            ("length", "frame_length_mismatch"),
            ("payload", "signal_mismatch"),
        ]:
            frame = copy.deepcopy(baseline)
            if fault == "id":
                frame.arbitration_id += 1
            elif fault == "extended":
                frame.is_extended_id = True
            elif fault == "fd":
                frame.is_fd = True
            elif fault == "remote":
                frame.is_remote_frame = True
            elif fault == "error":
                frame.is_error_frame = True
            elif fault == "length":
                frame.dlc += 1
            elif fault == "payload":
                frame.data[0] += 1
            local, peer = MagicMock(), MagicMock()
            peer.recv.return_value = frame
            with (
                self.subTest(fault=fault),
                patch(MODULE + ".open_bus", side_effect=[local, peer]),
            ):
                result = exchange_vector(self.database, vector, self.config)
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["status"], "failed")
            self.assertIsNotNone(result["observed"])
            local.shutdown.assert_called_once()
            peer.shutdown.assert_called_once()

    def test_standard_and_extended_filters_and_full_29_bit_identity(self):
        vector = copy.deepcopy(self.plan["vectors"][0])
        self.assertEqual(
            vector_filter(vector), {"can_id": 801, "can_mask": 0x7FF, "extended": False}
        )
        vector["frame_id"] = 0x18FF0321
        vector["is_extended_id"] = True
        self.assertEqual(
            vector_filter(vector),
            {"can_id": 0x18FF0321, "can_mask": 0x1FFFFFFF, "extended": True},
        )
        result = exchange_vector(self.database, vector, self.config)
        self.assertEqual(result["status"], "passed")
        receiver = open_bus(self.config, [vector_filter(vector)])
        sender = open_bus(self.config)
        try:
            # Same low 11 bits must not match a different extended ID or a standard frame.
            sender.send(
                can.Message(arbitration_id=0x321, is_extended_id=False, data=b"\0")
            )
            sender.send(
                can.Message(arbitration_id=0x10000321, is_extended_id=True, data=b"\0")
            )
            self.assertIsNone(receiver.recv(timeout=0.01))
        finally:
            sender.shutdown()
            receiver.shutdown()

    def test_open_send_receive_decode_and_shutdown_exceptions_cleanup(self):
        vector = self.plan["vectors"][0]
        for fault in [
            "first_open",
            "second_open",
            "send",
            "receive",
            "decode",
            "non_finite",
            "shutdown",
        ]:
            local, peer = MagicMock(), MagicMock()
            peer.recv.return_value = can.Message(
                arbitration_id=vector["frame_id"],
                is_extended_id=False,
                data=bytes.fromhex(vector["payload_hex"]),
            )
            opens = [local, peer]
            if fault == "first_open":
                opens = [RuntimeError("first open")]
            elif fault == "second_open":
                opens = [local, RuntimeError("second open")]
            elif fault == "send":
                local.send.side_effect = RuntimeError("send")
            elif fault == "receive":
                peer.recv.side_effect = RuntimeError("receive")
            elif fault == "shutdown":
                peer.shutdown.side_effect = RuntimeError("shutdown")
            database = (
                MagicMock() if fault in {"decode", "non_finite"} else self.database
            )
            if fault == "decode":
                database.get_message_by_name.side_effect = RuntimeError("decode")
            elif fault == "non_finite":
                database.get_message_by_name.return_value.decode.side_effect = [
                    vector["expected_raw_signals"],
                    {"CoolantTemperature": float("inf")},
                ]
            with (
                self.subTest(fault=fault),
                patch(MODULE + ".open_bus", side_effect=opens),
            ):
                result = exchange_vector(database, vector, self.config)
            self.assertEqual(result["status"], "failed")
            json.dumps(result, allow_nan=False)
            self.assertEqual(
                result["reason"],
                "cleanup_failed" if fault == "shutdown" else "runtime_error",
            )
            if fault != "first_open":
                local.shutdown.assert_called_once()
            if fault not in ["first_open", "second_open"]:
                peer.shutdown.assert_called_once()
            if fault == "shutdown":
                self.assertEqual(result["cleanup"][0]["status"], "failed")

    def test_invalid_inputs_and_configuration_never_probe_or_write(self):
        values = json.loads(self.declaration.read_text(encoding="utf-8"))
        values["vectors"][-1]["signals"]["Unknown"] = 1
        invalid = Path(self.temp.name) / "invalid.json"
        invalid.write_text(json.dumps(values), encoding="utf-8")
        cases = [
            (invalid, self.config),
            (self.declaration, BusConfig("virtual", "x", fd=True)),
            (self.declaration, BusConfig("virtual", "x", receive_own_messages=True)),
            (self.declaration, BusConfig("unknown", "x")),
        ]
        with (
            patch(MODULE + ".probe_can_backend") as probe,
            patch(MODULE + ".open_bus") as bus,
        ):
            for path, config in cases:
                with (
                    self.subTest(path=path, config=config),
                    self.assertRaises(ValueError),
                ):
                    run_declared_communication(
                        self.dbc, self.intent, path, config, self.output
                    )
                self.assertFalse(self.output.exists())
            probe.assert_not_called()
            bus.assert_not_called()

    def test_nonempty_output_preserved_and_input_drift_rejected(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with (
            patch(MODULE + ".probe_can_backend") as probe,
            self.assertRaises(ValueError),
        ):
            self.run_report()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        probe.assert_not_called()
        changed = copy.deepcopy(self.plan)
        changed["source_artifacts"][0]["sha256"] = "0" * 64
        with (
            patch(MODULE + ".preflight_communication", return_value=changed),
            patch(MODULE + ".probe_can_backend") as probe,
            self.assertRaisesRegex(ValueError, "changed"),
        ):
            self.run_report(output=self.output / "new")
        probe.assert_not_called()
        self.assertFalse((self.output / "new").exists())

    def test_missing_backend_produces_blocked_vectors_without_observations(self):
        with patch(MODULE + ".open_bus") as bus:
            report = self.run_report(config=BusConfig("socketcan", "wb-missing-p20"))
        self.assertEqual(report["status"], "blocked")
        self.assertIn(report["reason"], ["interface_missing", "unsupported_platform"])
        self.assertEqual(report["passed_count"], 0)
        for result in report["vectors"].values():
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["observed"])
            self.assertEqual(result["cleanup"], [])
        bus.assert_not_called()

    def test_probe_exception_is_reported_without_vector_execution(self):
        with (
            patch(
                MODULE + ".probe_can_backend", side_effect=RuntimeError("probe cleanup")
            ),
            patch(MODULE + ".open_bus") as bus,
        ):
            report = self.run_report()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["reason"], "probe_runtime_error")
        self.assertEqual(report["backend_probe"]["error"]["type"], "RuntimeError")
        self.assertTrue(
            all(item["observed"] is None for item in report["vectors"].values())
        )
        bus.assert_not_called()

    def test_send_and_receive_share_one_timeout_budget(self):
        local, peer = MagicMock(), MagicMock()
        peer.recv.return_value = None
        vector = self.plan["vectors"][0]
        with (
            patch(MODULE + ".open_bus", side_effect=[local, peer]),
            patch(MODULE + ".time.monotonic", side_effect=[1.0, 1.4]),
        ):
            result = exchange_vector(self.database, vector, self.config)
        self.assertEqual(result["reason"], "receive_timeout")
        self.assertEqual(local.send.call_args.kwargs["timeout"], 0.5)
        self.assertAlmostEqual(peer.recv.call_args.kwargs["timeout"], 0.1)

    def test_cli_success_failure_and_blocked_exit_codes(self):
        for case, code in [("success", 0), ("failed", 2), ("blocked", 3)]:
            args = [
                "workbench",
                "run-declared-communication",
                str(self.dbc),
                str(self.intent),
                str(self.declaration),
                "--output",
                str(self.output / case),
            ]
            if case == "blocked":
                args += ["--interface", "socketcan", "--channel", "wb-missing-p20"]
            real_exchange = exchange_vector

            def exchange(database, vector, config):
                if case == "failed":
                    with patch(
                        MODULE + ".open_bus",
                        side_effect=RuntimeError("controlled open failure"),
                    ):
                        return real_exchange(database, vector, config)
                return real_exchange(database, vector, config)

            with (
                patch("sys.argv", args),
                patch(MODULE + ".exchange_vector", side_effect=exchange),
                redirect_stdout(io.StringIO()) as stream,
            ):
                result_code = main()
            self.assertEqual(result_code, code)
            self.validator.validate(json.loads(stream.getvalue()))


if __name__ == "__main__":
    unittest.main()
