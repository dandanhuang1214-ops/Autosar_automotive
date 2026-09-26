"""Public ARXML project CLI cases, semantic diff and relocated review replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from run_arxml_scenarios import mutations, EVENT_ID  # noqa: E402
from automotive_workbench.arxml_bridge import digest, compare_imports, verify_report  # noqa: E402
from automotive_workbench.evidence_bundle import verify_evidence_bundle  # noqa: E402
from automotive_workbench.project_review import run_project_review  # noqa: E402
from automotive_workbench.project_comparison import (  # noqa: E402
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.review import validate_citations  # noqa: E402


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Scenario output must be empty or absent")
    output.mkdir(parents=True, exist_ok=True)
    source = output / "source"
    source.mkdir()
    project = read(ROOT / "examples/window_control/project-arxml.json")
    for key, relative in list(project["inputs"].items()):
        path = ROOT / "examples/window_control" / relative
        shutil.copyfile(path, source / path.name)
        project["inputs"][key] = path.name
    write(source / "project.json", project)
    data = (source / "model.arxml").read_bytes()
    variants = {
        "normal": data,
        **mutations(data),
        "unsupported": data.replace(b"</AUTOSAR>", b"<UNKNOWN-ELEMENT/></AUTOSAR>"),
    }
    producer = read(source / "provenance.json")
    results = {}
    mutation_record = {}
    for name, xml in variants.items():
        (source / "model.arxml").write_bytes(xml)
        provenance = (
            producer
            if name == "normal"
            else {
                "status": "synthetic-mutation",
                "baseline_sha256": digest(data),
                "mutation": name,
                "arxml_sha256": digest(xml),
            }
        )
        write(source / "provenance.json", provenance)
        mutation_record[name] = provenance
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "run-project",
                str(source / "project.json"),
                "--output",
                str(output / name),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        expected = 0 if name in {"normal", "period-change"} else 2
        if completed.returncode != expected:
            raise ValueError(
                f"{name}: {completed.returncode}: {completed.stdout} {completed.stderr}"
            )
        path = output / name / "bundle/project-report.json"
        report = read(path)
        if expected and report["stages"]["communication"] != {
            "status": "skipped",
            "path": None,
        }:
            raise ValueError("ARXML failure did not prevent communication")
        review = run_project_review(path, output / name / "review")
        if review["status"] != "answered":
            raise ValueError("Project review failed")
        results[name] = report["status"]
    write(output / "mutations.json", mutation_record)
    normal = output / "normal/bundle/project-report.json"
    for name in variants:
        comparison = compare_project_reports(
            normal,
            output / name / "bundle/project-report.json",
            output / (name + "-comparison"),
        )
        if comparison["status"] != ("stable" if name == "normal" else "not-comparable"):
            raise ValueError(f"Unexpected project comparison: {name}")
    baseline = read(output / "normal/bundle/arxml.json")["import"]
    candidate = read(output / "period-change/bundle/arxml.json")["import"]
    semantic = compare_imports(baseline, candidate)
    verify_report(semantic)
    if semantic["status"] != "changed" or [c["id"] for c in semantic["changes"]] != [
        EVENT_ID
    ]:
        raise ValueError("ARXML semantic diff differs from golden")
    write(output / "semantic-diff.json", semantic)
    shutil.rmtree(source)  # Only scenario-generated inputs.
    moved = output.with_name(output.name + "-relocated")
    if moved.exists():
        raise ValueError("Relocation destination already exists")
    output.rename(moved)
    for name in variants:
        root = moved / name
        if (
            verify_evidence_bundle(
                root / "bundle",
                root / "manifest.json",
                root / "reverification",
                base=root,
            )["status"]
            != "passed"
        ):
            raise ValueError("Relocated bundle failed")
        if (
            validate_citations(
                root / "review/review-request.json",
                read(root / "review/review-result.json"),
            )["status"]
            != "passed"
        ):
            raise ValueError("Relocated citations failed")
        if (
            run_project_review(root / "bundle/project-report.json", root / "rereview")[
                "status"
            ]
            != "answered"
        ):
            raise ValueError("Relocated review failed")
        if (
            validate_project_comparison(
                moved / (name + "-comparison") / "project-comparison.json"
            )["status"]
            != "passed"
        ):
            raise ValueError("Relocated comparison failed")
        verify_report(read(root / "bundle/arxml.json")["import"])
    summary = {
        "status": "passed",
        "cases": results,
        "relocated_replays": len(variants),
        "semantic_changed_ids": [EVENT_ID],
    }
    write(moved / "summary.json", summary)
    moved.rename(output)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
