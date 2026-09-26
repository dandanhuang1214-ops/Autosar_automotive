"""Reproduce normal/dangling/period-change CLI evidence from real exported XML."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from automotive_workbench.arxml_bridge import digest, verify_report  # noqa: E402

EVENT_ID = "/ComponentTypes/WindowControlSwc/WindowControlSwc_InternalBehavior/TMT_WindowControl_Step"
REF = (
    '<TYPE-TREF DEST="APPLICATION-DATA-TYPE">/DataTypes/App_WindowPosition</TYPE-TREF>'
)


def mutations(data: bytes) -> dict[str, bytes]:
    text = data.decode("utf-8")
    if text.count(REF) != 1 or text.count("<PERIOD>0.01</PERIOD>") != 1:
        raise ValueError("Golden mutation anchors must occur exactly once")
    return {
        "dangling": text.replace(
            REF, REF.replace("App_WindowPosition", "AbsentType")
        ).encode(),
        "period-change": text.replace(
            "<PERIOD>0.01</PERIOD>", "<PERIOD>0.02</PERIOD>"
        ).encode(),
    }


def run(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Scenario output must be empty or absent")
    output.mkdir(parents=True, exist_ok=True)
    inputs = output / "inputs"
    inputs.mkdir()
    fixture = ROOT / "examples/generate_arxml/xml"
    shutil.copyfile(fixture / "model.arxml", inputs / "baseline.arxml")
    baseline = inputs / "baseline.arxml"
    changes = mutations(baseline.read_bytes())
    mutation_record: dict = {"source_sha256": digest(baseline.read_bytes()), "mutations": {}}
    for name, data in changes.items():
        (inputs / f"{name}.arxml").write_bytes(data)
        mutation_record["mutations"][name] = digest(data)
    (output / "mutations.json").write_text(
        json.dumps(mutation_record, indent=2) + "\n", encoding="utf-8"
    )

    def cli(name: str, arguments: list[str], expected: int) -> dict:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                *arguments,
                "--output",
                str(output / name),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != expected:
            raise ValueError(
                f"{name}: exit {completed.returncode}, expected {expected}: {completed.stdout} {completed.stderr}"
            )
        report = json.loads(
            (output / name / "arxml-report.json").read_text(encoding="utf-8")
        )
        verify_report(report)
        return report

    normal = cli(
        "normal",
        [
            "import-arxml",
            str(baseline),
            "--provenance",
            str(fixture / "provenance.json"),
        ],
        0,
    )
    dangling = cli("dangling", ["import-arxml", str(inputs / "dangling.arxml")], 2)
    stable = cli("stable", ["compare-arxml", str(baseline), str(baseline)], 0)
    changed = cli(
        "changed",
        ["compare-arxml", str(baseline), str(inputs / "period-change.arxml")],
        2,
    )
    rejected = cli(
        "rejected", ["compare-arxml", str(baseline), str(inputs / "dangling.arxml")], 2
    )
    observed = dict(
        objects=len(normal["objects"]),
        references=len(normal["references"]),
        baseline_status=normal["status"],
        coverage=normal["coverage"],
        dangling_codes=[f["code"] for f in dangling["findings"]],
        stable_status=stable["status"],
        changed_status=changed["status"],
        changed_ids=[c["id"] for c in changed["changes"]],
        rejected_status=rejected["status"],
    )
    expected = json.loads((fixture / "golden.json").read_text(encoding="utf-8"))
    if observed != expected:
        raise ValueError(f"Golden differs: {observed}")
    # Remove only inputs created by this scenario; embedded reports must stand alone.
    shutil.rmtree(inputs)
    relocated = output / "relocated"
    relocated.mkdir()
    for name in ["normal", "dangling", "stable", "changed", "rejected"]:
        shutil.move(str(output / name), str(relocated / name))
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "verify-arxml",
                str(relocated / name / "arxml-report.json"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode:
            raise ValueError(f"Relocated {name} failed: {completed.stdout}")
    summary = dict(status="passed", cases=5, relocated_replays=5, observed=observed)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
