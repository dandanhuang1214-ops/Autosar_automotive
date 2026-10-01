"""Full P26 review/change workflow; synthetic inputs and optional isolated consumer."""

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
CASES: dict[str, tuple[str, str, str] | None] = {
    "normal": None,
    "signal": ("modules.arxml", "<VALUE>8</VALUE>", "<VALUE>12</VALUE>"),
    "pdu": ("modules.arxml", "/Demo/EcuC/C</VALUE-REF>", "/Demo/EcuC/D</VALUE-REF>"),
    "task": (
        "modules.arxml",
        "/Demo/Os/TaskA</VALUE-REF>",
        "/Demo/Os/TaskB</VALUE-REF>",
    ),
    "period": ("application.arxml", "<PERIOD>0.010</PERIOD>", "<PERIOD>0.020</PERIOD>"),
    "mode": ("modules.arxml", "BSWM_EQUALS", "BSWM_EQUALS_NOT"),
    "unbound": ("modules.arxml", "/Demo/Os/TaskA</VALUE-REF>", "</VALUE-REF>"),
    "duplicate": (
        "modules.arxml",
        "<SHORT-NAME>TaskB</SHORT-NAME>",
        "<SHORT-NAME>TaskA</SHORT-NAME>",
    ),
    "opaque": (
        "modules.arxml",
        "<SHORT-NAME>ValueA</SHORT-NAME>",
        "<SHORT-NAME>ValueA</SHORT-NAME><VENDOR-EXTENSION>new</VENDOR-EXTENSION>",
    ),
    "historical": (
        "tool.log",
        "Historical task binding failure",
        "Later historical observation",
    ),
}


def run(output: Path, cli_python: Path | None = None) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Scenario output must be absent")
    output = output.resolve()
    output.mkdir(parents=True)
    work = output / "original"
    env = {**os.environ, "PYTHONUTF8": "1"}
    if cli_python:
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    # Keep the venv launcher path: resolving its symlink would select the base interpreter.
    interpreter = str(cli_python.absolute()) if cli_python else sys.executable

    def cli(name: str, args: list[str], code: int) -> dict[str, Any]:
        proc = subprocess.run(
            [interpreter, "-m", "automotive_workbench.cli", *args],
            env=env,
            cwd=output,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
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
        if proc.returncode != code:
            raise ValueError(
                f"{name}: expected {code}, got {proc.returncode}: {proc.stdout} {proc.stderr}"
            )
        return json.loads(proc.stdout)

    reviews, comparisons = [], []
    for name, mutation in CASES.items():
        source = work / "inputs" / name
        shutil.copytree(ROOT / "tests/fixtures/ecuc-engineering", source)
        if mutation:
            file, before, after = mutation
            p = source / file
            p.write_text(
                p.read_text(encoding="utf-8").replace(before, after, 1),
                encoding="utf-8",
            )
        code = 2 if name in {"unbound", "duplicate", "pdu"} else 0
        result = cli(
            "review-" + name,
            [
                "review-ecuc-project",
                str(source / "demo.dpa"),
                "--application",
                str(source / "application.arxml"),
                "--tool-log",
                str(source / "tool.log"),
                "--output",
                str(work / "reviews" / name),
            ],
            code,
        )
        reviews.append(
            {"case": name, "status": result["status"], "summary": result["summary"]}
        )
        if name == "normal" and (
            result["summary"]["task_bindings"] != 2
            or result["summary"]["mode_rules"] != 1
            or result["historical_tool_logs"][0]["binding"] != "historical-unbound"
        ):
            raise ValueError("Incomplete combined baseline")
        delta = cli(
            "compare-" + name,
            [
                "compare-ecuc-reviews",
                str(work / "reviews/normal/ecuc-review.json"),
                str(work / "reviews" / name / "ecuc-review.json"),
                "--output",
                str(work / "comparisons" / name),
            ],
            2 if name in {"opaque", "duplicate"} else 0,
        )
        expected = (
            "not-comparable"
            if name == "duplicate"
            else "partial"
            if name == "opaque"
            else "unchanged-in-scope"
            if name in {"normal", "historical"}
            else "changed-in-scope"
        )
        if delta["status"] != expected:
            raise ValueError(f"{name}: impact status {delta['status']} != {expected}")
        if name == "signal" and (
            {x["com_ipdu"] for x in delta["communication_impacts"]}
            != {"/Demo/Com/PacketA"}
            or delta["binding_impacts"]
        ):
            raise ValueError("Signal change escaped expected Tx path")
        if name == "task" and (
            {x["mapping"] for x in delta["binding_impacts"]}
            != {"ecuc:/Demo/Rte/Instance/Mapping"}
            or delta["communication_impacts"]
        ):
            raise ValueError("Task rebinding escaped expected mapping")
        if name == "mode" and (
            {x["rule"] for x in delta["mode_impacts"]} != {"ecuc:/Demo/BswM/Rule"}
            or delta["binding_impacts"]
        ):
            raise ValueError("Mode change escaped expected rule")
        comparisons.append(
            {"case": name, "status": delta["status"], "summary": delta["summary"]}
        )
    # Retain only self-contained comparisons; review/input originals are gone during replay.
    moved = output / "portable"
    work.rename(moved)
    shutil.rmtree(moved / "inputs")
    shutil.rmtree(moved / "reviews")
    for name in CASES:
        r = cli(
            "replay-" + name,
            [
                "verify-ecuc-impact",
                str(moved / "comparisons" / name / "ecuc-impact.json"),
            ],
            0,
        )
        if r["status"] != "passed":
            raise ValueError("Portable comparison failed")
    for kind in ("conclusion", "source", "html", "inventory"):
        forged = moved / ("forged-" + kind)
        shutil.copytree(moved / "comparisons/signal", forged)
        if kind == "conclusion":
            p = forged / "ecuc-impact.json"
            r = json.loads(p.read_text(encoding="utf-8"))
            r["affected_objects"] = []
            p.write_text(json.dumps(r), encoding="utf-8")
        elif kind == "source":
            p = forged / "after/snapshot/project/modules.arxml"
            p.write_bytes(p.read_bytes().replace(b">12<", b">16<"))
        elif kind == "html":
            (forged / "after/index.html").write_text("forged display", encoding="utf-8")
        else:
            (forged / "after/snapshot/extra.txt").write_text(
                "unexpected", encoding="utf-8"
            )
        cli(
            "reject-" + kind,
            ["verify-ecuc-impact", str(forged / "ecuc-impact.json")],
            1,
        )
    result = {
        "status": "passed",
        "consumer": "installed" if cli_python else "source",
        "reviews": reviews,
        "comparisons": comparisons,
        "migrations": len(CASES),
        "tamper_rejections": 4,
        "scope": "Synthetic engineering structure; no vendor or physical ECU execution.",
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cli-python", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.cli_python), indent=2))
