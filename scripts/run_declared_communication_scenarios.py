"""P20b: real CLI successes and explicitly injected virtual transport failures."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from automotive_workbench.can_io import BusConfig, open_bus
from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.declared_communication import run_declared_communication

ROOT = Path(__file__).resolve().parents[1]


class FaultEndpoint:
    """Wrap a real virtual endpoint; only the test's send operation is changed."""

    def __init__(self, bus: Any, mode: str, sends: list[dict[str, Any]]):
        self.bus, self.mode, self.sends = bus, mode, sends

    def send(self, message: Any, **kwargs: Any) -> None:
        message = copy.copy(message)
        if self.mode == "wrong_id":
            message.arbitration_id += 1
        self.sends.append(
            {
                "frame_id": message.arbitration_id,
                "payload_hex": bytes(message.data).hex(),
                "suppressed": self.mode == "no_send",
            }
        )
        if self.mode != "no_send":
            self.bus.send(message, **kwargs)

    def recv(self, **kwargs: Any) -> Any:
        return self.bus.recv(**kwargs)

    def shutdown(self) -> None:
        self.bus.shutdown()


def run_scenarios(output: Path) -> None:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Scenario output must be empty or absent")
    output.mkdir(parents=True, exist_ok=True)
    validator = Draft202012Validator(
        json.loads(
            (ROOT / "schemas/declared-communication-runtime.schema.json").read_text(
                encoding="utf-8"
            )
        ),
        format_checker=FormatChecker(),
    )
    summary = []
    for name in ["window_control", "thermal_control"]:
        root = ROOT / "examples" / name
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "run-declared-communication",
                str(root / (name + ".dbc")),
                str(root / "bsw_intent.json"),
                str(root / "communication_vectors.json"),
                "--output",
                str(output / name),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        report = json.loads(process.stdout)
        validator.validate(report)
        if report["status"] != "passed":
            raise RuntimeError(f"{name}: runtime did not pass")
        summary.append(
            {
                "case": name,
                "status": report["status"],
                "passed_count": report["passed_count"],
            }
        )
    root = ROOT / "examples/thermal_control"
    declaration = json.loads(
        (root / "communication_vectors.json").read_text(encoding="utf-8")
    )
    for vector in declaration["vectors"]:
        vector["timeout_seconds"] = 0.02
    fault_declaration = output / "fault-vectors.json"
    fault_declaration.write_text(
        json.dumps(declaration, indent=2) + "\n", encoding="utf-8"
    )
    for mode in ["wrong_id", "no_send"]:
        sends: list[dict[str, Any]] = []

        def factory(config: BusConfig, filters: list[dict[str, Any]]) -> FaultEndpoint:
            return FaultEndpoint(open_bus(config, filters), mode, sends)

        with patch(
            "automotive_workbench.declared_communication.open_bus", side_effect=factory
        ):
            report = run_declared_communication(
                root / "thermal_control.dbc",
                root / "bsw_intent.json",
                fault_declaration,
                default_communication_config(),
                output / mode,
            )
        validator.validate(report)
        if report["status"] != "failed" or not all(
            item["reason"] == "receive_timeout" and item["observed"] is None
            for item in report["vectors"].values()
        ):
            raise RuntimeError(f"{mode}: expected transport failure was not detected")
        (output / mode / "injection.json").write_text(
            json.dumps(
                {
                    "method": "in-process send interception on real python-can virtual endpoints",
                    "fault": mode,
                    "sends": sends,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary.append(
            {"case": mode, "status": report["status"], "reason": "receive_timeout"}
        )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "run-declared-communication",
            str(root / "thermal_control.dbc"),
            str(root / "bsw_intent.json"),
            str(root / "communication_vectors.json"),
            "--interface",
            "socketcan",
            "--channel",
            "wb-missing-p20",
            "--output",
            str(output / "blocked"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    report = json.loads(process.stdout)
    validator.validate(report)
    if process.returncode != 3 or report["status"] != "blocked":
        raise RuntimeError("Missing backend must return blocked / exit 3")
    summary.append(
        {"case": "blocked", "status": report["status"], "reason": report["reason"]}
    )
    (output / "summary.json").write_text(
        json.dumps({"cases": summary}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run_scenarios(parser.parse_args().output)
