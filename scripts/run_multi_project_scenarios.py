"""P20 end-to-end release scenarios, including relocation with original paths removed."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.evidence_bundle import verify_evidence_bundle
from automotive_workbench.project_workflow import run_project
from automotive_workbench.project_review import run_project_review
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.review import validate_citations

ROOT = Path(__file__).resolve().parents[1]


def run_scenarios(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("P20 scenario output must be absent or empty")
    original = output / "original"
    original.mkdir(parents=True)
    cases = {
        "window": ("window_control", "project-declared.json"),
        "thermal": ("thermal_control", "project.json"),
        "static-failure": ("thermal_control", "project.json"),
        "runtime-failure": ("thermal_control", "project.json"),
        "changed-definition": ("thermal_control", "project.json"),
        "blocked": ("thermal_control", "project.json"),
    }
    results = {}
    for name, (fixture, project_file) in cases.items():
        source = original / "sources" / name
        shutil.copytree(ROOT / "examples" / fixture, source)
        if name == "static-failure":
            contract = source / "canonical_contract.json"
            value = json.loads(contract.read_text(encoding="utf-8"))
            value["signals"][0]["resolution"] = "2"
            contract.write_text(json.dumps(value), encoding="utf-8")
        if name == "changed-definition":
            project = source / project_file
            value = json.loads(project.read_text(encoding="utf-8"))
            value["requirements"][-1]["expected"] = 0
            project.write_text(json.dumps(value), encoding="utf-8")
        target = original / "projects" / name
        if name == "runtime-failure":
            # Keep valid inputs. A real virtual receiver times out when sender is suppressed.
            from automotive_workbench.can_io import open_bus
            from run_declared_communication_scenarios import FaultEndpoint

            sends: list[dict] = []

            def factory(config, filters):
                return FaultEndpoint(open_bus(config, filters), "no_send", sends)

            with patch(
                "automotive_workbench.declared_communication.open_bus",
                side_effect=factory,
            ):
                result = run_project(
                    source / project_file, target, default_communication_config()
                )
            (original / "transport-injection.json").write_text(
                json.dumps(
                    {
                        "method": "in-process send suppression on real virtual endpoints",
                        "sends": sends,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            code = 2 if result["status"] == "failed" else 0
        else:
            command = [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "run-project",
                str(source / project_file),
                "--output",
                str(target),
            ]
            if name == "blocked":
                command.extend(
                    ["--interface", "socketcan", "--channel", "wb-missing-p20"]
                )
            process = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8"
            )
            code = process.returncode
            result = json.loads(process.stdout)
        expected = (
            "passed"
            if name in {"window", "thermal"}
            else "blocked"
            if name == "blocked"
            else "failed"
        )
        if (
            result.get("status") != expected
            or code != {"passed": 0, "failed": 2, "blocked": 3}[expected]
        ):
            raise RuntimeError(f"{name}: unexpected project result {result}")
        results[name] = {
            "status": result["status"],
            "integrity_status": result["integrity_status"],
        }
        report = target / "bundle/project-report.json"
        payload = json.loads(report.read_text(encoding="utf-8"))
        if (
            name == "static-failure"
            and payload["stages"]["communication"]["status"] != "skipped"
        ):
            raise RuntimeError("Static failure did not gate runtime")
        review = run_project_review(report, original / "reviews" / name)
        if (
            review["status"] != "answered"
            or review["citation_validation"]["status"] != "passed"
        ):
            raise RuntimeError(f"{name}: review failed")
    comparisons = {
        "stable": ("thermal", "thermal", "stable"),
        "static-regression": ("thermal", "static-failure", "regressed"),
        "runtime-regression": ("thermal", "runtime-failure", "regressed"),
        "changed-definition": ("thermal", "changed-definition", "not-comparable"),
        "different-project": ("thermal", "window", "not-comparable"),
    }
    for name, (left, right, expected) in comparisons.items():
        result = compare_project_reports(
            original / "projects" / left / "bundle/project-report.json",
            original / "projects" / right / "bundle/project-report.json",
            original / "comparisons" / name,
        )
        if (
            result["status"] != expected
            or result["evidence_validation"]["status"] != "passed"
        ):
            raise RuntimeError(f"{name}: comparison mismatch: {result['status']}")
    # Move, rather than copy, so every original path is now absent.
    portable = output / "portable"
    original.rename(portable)
    for name in cases:
        project = portable / "projects" / name
        integrity = verify_evidence_bundle(
            project / "bundle",
            project / "manifest.json",
            portable / "reverification" / name,
            base=project,
        )
        if integrity["status"] != "passed":
            raise RuntimeError(f"{name}: moved bundle failed integrity")
        review_dir = portable / "reviews" / name
        review_result = json.loads(
            (review_dir / "review-result.json").read_text(encoding="utf-8")
        )
        if (
            validate_citations(review_dir / "review-request.json", review_result)[
                "status"
            ]
            != "passed"
        ):
            raise RuntimeError(f"{name}: moved citations failed")
        # Also reread 0.3's portable source inventory after movement.
        rerun = run_project_review(
            project / "bundle/project-report.json", portable / "rereviews" / name
        )
        if rerun["status"] != "answered":
            raise RuntimeError(f"{name}: moved project could not be reviewed")
    for name in comparisons:
        if (
            validate_project_comparison(
                portable / "comparisons" / name / "project-comparison.json"
            )["status"]
            != "passed"
        ):
            raise RuntimeError(f"{name}: moved comparison invalid")
    rows = "".join(
        f'<li><a href="projects/{name}/bundle/index.html">{name}: {result["status"]}</a> · <a href="reviews/{name}/project-review.md">review</a></li>'
        for name, result in results.items()
    )
    links = "".join(
        f'<li><a href="comparisons/{name}/index.html">{name}</a></li>'
        for name in comparisons
    )
    (portable / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>P20 multi-project acceptance</title><h1>P20 multi-project acceptance</h1><p>Public synthetic inputs; two in-process CAN endpoints. No physical ECU evidence.</p><h2>Projects and reviews</h2><ul>'
        + rows
        + "</ul><h2>Comparisons</h2><ul>"
        + links
        + "</ul>",
        encoding="utf-8",
    )
    summary = {
        "status": "passed",
        "cases": results,
        "comparisons": {name: v[2] for name, v in comparisons.items()},
        "relocation": "passed; original directory absent",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run_scenarios(parser.parse_args().output), indent=2))
