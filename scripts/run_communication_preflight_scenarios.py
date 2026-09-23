"""Archive two real CLI preflights and a rejected declaration; no CAN runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def run_scenarios(output: Path) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Scenario output must be absent or empty")
    results = {}
    validator = Draft202012Validator(
        json.loads(
            (ROOT / "schemas/communication-plan.schema.json").read_text(
                encoding="utf-8"
            )
        )
    )
    for name in ("window_control", "thermal_control"):
        root = ROOT / "examples" / name
        command = [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "plan-communication",
            str(root / (name + ".dbc")),
            str(root / "bsw_intent.json"),
        ]
        process = subprocess.run(
            command + [str(root / "communication_vectors.json")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        result = json.loads(process.stdout)
        validator.validate(result)
        results[name] = result
    declaration = json.loads(
        (root / "communication_vectors.json").read_text(encoding="utf-8")
    )
    declaration["vectors"][0]["signals"] = {"UnknownSignal": 1}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "invalid.json"
        path.write_text(json.dumps(declaration), encoding="utf-8")
        process = subprocess.run(
            command + [str(path)], capture_output=True, text=True, encoding="utf-8"
        )
        result = json.loads(process.stdout)
        if process.returncode != 1 or result.get("status") != "error":
            raise RuntimeError("Invalid declaration was not rejected")
        results["unknown-signal-rejection"] = result
    output.mkdir(parents=True, exist_ok=True)
    for name, result in results.items():
        (output / (name + ".json")).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(
        "Two CLI plans validated; unknown-signal declaration rejected. No bus opened."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run_scenarios(parser.parse_args().output)
