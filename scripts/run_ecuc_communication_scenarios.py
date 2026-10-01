"""Public synthetic ECUC chains, negative cases and portable CLI replay."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "normal": None,
    "missing": ("/Demo/Can/ObjectA", "/Demo/Can/Missing"),
    "wrong-type": ("/Demo/Can/ObjectA", "/Demo/Can/Controller"),
    "external": ("/Demo/Can/ObjectA", "/Other/ObjectA"),
    "duplicate": (
        "<SHORT-NAME>ObjectB</SHORT-NAME>",
        "<SHORT-NAME>ObjectA</SHORT-NAME>",
    ),
    "direction": (">TRANSMIT<", ">RECEIVE<"),
    "vendor-link": ("CanIfHthIdSymRef", "VendorHardwareLink"),
    "conditional": (
        "<SHORT-NAME>ObjectA</SHORT-NAME>",
        "<SHORT-NAME>ObjectA</SHORT-NAME><VARIATION-POINT/>",
    ),
    "no-paths": ("/Synthetic/ComIPdu<", "/Synthetic/OtherIPdu<"),
}


def run(output: Path) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Scenario output must be absent")
    output = output.resolve()
    work = output / "original"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}

    def cli(name: str, args: list[str], expected: int) -> dict[str, Any]:
        proc = subprocess.run(
            [sys.executable, "-m", "automotive_workbench.cli", *args],
            env=env,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        output.mkdir(parents=True, exist_ok=True)
        (output / (name + ".json")).write_text(
            json.dumps(
                {
                    "argv": args,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if proc.returncode != expected:
            raise ValueError(
                f"{name}: expected {expected}, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            )
        return json.loads(proc.stdout)

    rows = []
    for name, mutation in CASES.items():
        source = work / "inputs" / name
        shutil.copytree(ROOT / "tests/fixtures/ecuc-communication", source)
        if mutation:
            p = source / "modules.arxml"
            p.write_text(
                p.read_text(encoding="utf-8").replace(*mutation), encoding="utf-8"
            )
        r = cli(
            name,
            [
                "trace-ecuc-communication",
                str(source / "demo.dpa"),
                "--output",
                str(work / "reports" / name),
            ],
            0 if name == "normal" else 2,
        )
        if name == "normal":
            if [p["direction"] for p in r["paths"]] != ["tx", "rx"] or any(
                p["gaps"] for p in r["paths"]
            ):
                raise ValueError("Normal two-direction chain incomplete")
            if r["paths"][1]["members"][-1]["group"] != "/Demo/Com/GroupB":
                raise ValueError("Group signal membership absent")
        elif name == "no-paths":
            if r["status"] != "no-paths" or r["paths"]:
                raise ValueError("Unsupported Com container claimed a path")
        elif r["status"] != "partial" or r["paths"][0]["status"] != "partial":
            raise ValueError("Incomplete Tx path accepted")
        rows.append(
            {
                "case": name,
                "status": r["status"],
                "path_count": len(r["paths"]),
                "resolved": sum(p["status"] == "resolved" for p in r["paths"]),
            }
        )
    moved = output / "portable"
    work.rename(moved)
    shutil.rmtree(moved / "inputs")
    for name in CASES:
        r = cli(
            "replay-" + name,
            [
                "verify-ecuc-communication",
                str(moved / "reports" / name / "ecuc-communication.json"),
            ],
            0,
        )
        if r["status"] != "passed":
            raise ValueError("Portable replay failed")
    for tamper_kind in ["conclusion", "source", "inventory"]:
        forged = moved / ("forged-" + tamper_kind)
        shutil.copytree(moved / "reports/normal", forged)
        path = forged / "ecuc-communication.json"
        if tamper_kind == "conclusion":
            r = json.loads(path.read_text(encoding="utf-8"))
            r["paths"][0]["direction"] = "rx"
            path.write_text(json.dumps(r), encoding="utf-8")
        elif tamper_kind == "source":
            p = forged / "snapshot/modules.arxml"
            p.write_bytes(p.read_bytes().replace(b">SEND<", b">RECEIVE<"))
        else:
            (forged / "snapshot/extra.txt").write_text("unlisted", encoding="utf-8")
        r = cli("reject-" + tamper_kind, ["verify-ecuc-communication", str(path)], 1)
        if r["status"] != "error":
            raise ValueError("Tamper accepted")
    result = {
        "status": "passed",
        "cases": rows,
        "migrations": len(rows),
        "tamper_rejections": 3,
        "scope": "Synthetic structural references only; no vendor or physical ECU validation.",
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
