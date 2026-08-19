from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from automotive_workbench.can_io import (
    BusConfig,
    capture_log,
    decode_log,
    open_bus,
    replay_log,
    sha256_file,
)
from automotive_workbench.can_runtime import _python_can


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"


class CanIoTests(unittest.TestCase):
    def test_capture_decode_and_replay_preserve_frames(self) -> None:
        can = _python_can()
        channel = f"can-io-{uuid.uuid4()}"
        config = BusConfig("virtual", channel)
        sender = open_bus(config)
        receiver = open_bus(config)
        try:
            for value in (40, 41, 42):
                sender.send(can.Message(
                    arbitration_id=0x100,
                    data=bytes([value, 0, 0, 0, 0, 0, 0, 0]),
                    is_extended_id=False,
                ))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                capture = capture_log(receiver, root / "capture", 3, 1.0, config)
                log = root / "capture" / "capture.log"
                analysis = decode_log(log, DBC, root / "decode")

                replay_channel = f"can-replay-{uuid.uuid4()}"
                replay_config = BusConfig("virtual", replay_channel)
                replay_sender = open_bus(replay_config)
                replay_receiver = open_bus(replay_config)
                try:
                    replay = replay_log(
                        log,
                        replay_sender,
                        timestamps=False,
                        gap_s=0.001,
                        output=root / "replay",
                        config=replay_config,
                    )
                    replayed = [replay_receiver.recv(timeout=0.1) for _ in range(3)]
                finally:
                    replay_sender.shutdown()
                    replay_receiver.shutdown()

                manifest = json.loads(
                    (root / "capture" / "capture.manifest.json").read_text(encoding="utf-8")
                )
                replay_report = json.loads(
                    (root / "replay" / "replay-report.json").read_text(encoding="utf-8")
                )
                decode_markdown = (root / "decode" / "decode-report.md").read_text(encoding="utf-8")
        finally:
            sender.shutdown()
            receiver.shutdown()

        self.assertEqual(capture["status"], "passed")
        self.assertEqual(manifest["log_sha256"], capture["log_sha256"])
        self.assertEqual(analysis["status"], "passed")
        self.assertEqual([item["signals"]["WindowPosition"] for item in analysis["decoded"]], [40, 41, 42])
        self.assertEqual(replay["sent_count"], 3)
        self.assertEqual(replay_report["timing_mode"], "fixed-gap")
        self.assertEqual([message.arbitration_id for message in replayed], [0x100, 0x100, 0x100])
        self.assertEqual([message.data[0] for message in replayed], [40, 41, 42])
        self.assertIn("raw log remains the source frame evidence", decode_markdown)

    def test_decode_reports_unknown_id(self) -> None:
        can = _python_can()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "unknown.log"
            writer = can.Logger(str(log))
            writer.on_message_received(can.Message(
                timestamp=1.0,
                arbitration_id=0x777,
                data=bytes(8),
                is_extended_id=False,
                channel="virtual",
            ))
            writer.stop()
            result = decode_log(log, DBC, root / "decode")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["findings"][0]["code"], "LOG-UNKNOWN-FRAME-ID")


if __name__ == "__main__":
    unittest.main()
