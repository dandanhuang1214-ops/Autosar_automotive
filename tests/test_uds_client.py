from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.can_io import BusConfig, open_bus, sha256_file
from automotive_workbench.uds_client import load_did_profile, read_uds_did


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "examples/openbsw/read_cf01.json"


@contextmanager
def independent_ecu(config, payload, response_id=240):
    """An independent ISO-TP peer; no production responder or UDS client mocks."""
    import can
    import isotp

    bus = open_bus(config)
    notifier = can.Notifier(bus, [], timeout=0.01)
    stack = isotp.NotifierBasedCanStack(
        bus,
        notifier,
        address=isotp.Address(
            isotp.AddressingMode.Normal_11bits, txid=response_id, rxid=42
        ),
        params={"tx_padding": 0},
    )
    stopped = threading.Event()
    requests = []

    def serve():
        while not stopped.is_set():
            request = stack.recv(block=True, timeout=0.02)
            if request is not None:
                requests.append(bytes(request))
                if payload is not None:
                    stack.send(payload)

    stack.start()
    thread = threading.Thread(target=serve)
    thread.start()
    try:
        yield requests
    finally:
        stopped.set()
        thread.join(timeout=2)
        stack.stop()
        notifier.stop()
        bus.shutdown()


class UdsClientTests(unittest.TestCase):
    def test_external_multiframe_read_and_faults(self):
        profile, _ = load_did_profile(PROFILE)
        expected = bytes.fromhex(profile["expected_data_hex"])
        cases = [
            (b"\x62\xcf\x01" + expected, 240, "passed", ""),
            (b"\x62\xcf\x01" + bytes(24), 240, "failed", "data_mismatch"),
            (b"\x7f\x22\x31", 240, "failed", "negative_response"),
            (b"\x62\xcf\x01\x00", 240, "failed", "invalid_response"),
            (b"\x62\xcf\x02" + expected, 240, "failed", "unexpected_response"),
            (None, 240, "failed", "timeout"),
            (b"\x7f\x22\x31", 241, "failed", "timeout"),
        ]
        validator = Draft202012Validator(
            json.loads((ROOT / "schemas/uds-did-read.schema.json").read_text()),
            format_checker=FormatChecker(),
        )
        for payload, response_id, status, reason in cases:
            with (
                self.subTest(reason=reason),
                tempfile.TemporaryDirectory() as directory,
            ):
                config = BusConfig("virtual", "did-test-" + uuid.uuid4().hex)
                path = Path(directory) / "profile.json"
                path.write_text(json.dumps({**profile, "timeout_s": 0.3}))
                with independent_ecu(config, payload, response_id) as requests:
                    result = read_uds_did(path, config, Path(directory) / "result")
                self.assertEqual((result["status"], result["reason"]), (status, reason))
                self.assertEqual(requests, [b"\x22\xcf\x01"])
                validator.validate(result)
                self.assertEqual(result["profile"]["sha256"], sha256_file(path))
                self.assertEqual(
                    result["capture"]["sha256"],
                    sha256_file(Path(result["capture"]["source"])),
                )
                if status == "passed":
                    self.assertEqual(
                        result["actual_data_hex"], profile["expected_data_hex"]
                    )
                    types = [f["pci_type"] for f in result["frames"]]
                    for frame_type in ("SF", "FF", "FC", "CF"):
                        self.assertIn(frame_type, types)
                if reason == "negative_response":
                    self.assertEqual(result["negative_response_code"], 0x31)

    def test_blocked_preserves_evidence_and_cli_exit_code(self):
        from automotive_workbench.cli import main

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "blocked"
            args = [
                "workbench",
                "read-uds-did",
                str(PROFILE),
                "--interface",
                "socketcan",
                "--channel",
                "absent-did-test",
                "--output",
                str(output),
            ]
            with patch("sys.argv", args), patch("builtins.print"):
                self.assertEqual(main(), 3)
            report = json.loads((output / "uds-did-report.json").read_text())
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["frames"], [])
            self.assertIsNone(report["capture"])
            self.assertTrue((output / "uds-did-report.md").exists())

    def test_invalid_profiles_rejected_before_probe(self):
        original, _ = load_did_profile(PROFILE)
        schema = json.loads((ROOT / "schemas/uds-did-profile.schema.json").read_text())
        mutations = [
            {"did": True},
            {"request_id": 2048},
            {"response_id": -1},
            {"expected_data_hex": "0"},
            {"expected_data_hex": "ab"},
            {"timeout_s": True},
            {"timeout_s": 0},
            {"target": " "},
            {"service": "ECUReset"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for changes in mutations:
                with self.subTest(changes=changes):
                    profile = {**original, **changes}
                    path.write_text(json.dumps(profile))
                    self.assertFalse(Draft202012Validator(schema).is_valid(profile))
                    with patch(
                        "automotive_workbench.uds_client.probe_uds_backend"
                    ) as probe:
                        with self.assertRaises(ValueError):
                            read_uds_did(
                                path,
                                BusConfig("virtual", "unused"),
                                Path(directory) / "out",
                            )
                        probe.assert_not_called()
            for changes in (
                {"request_id": original["response_id"]},
                {"timeout_s": float("nan")},
            ):
                path.write_text(json.dumps({**original, **changes}))
                with self.assertRaises(ValueError):
                    load_did_profile(path)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / "existing.txt"
            sentinel.write_text("user data")
            with self.assertRaisesRegex(ValueError, "empty directory"):
                read_uds_did(PROFILE, BusConfig("virtual", "unused"), output)
            self.assertEqual(sentinel.read_text(), "user data")
