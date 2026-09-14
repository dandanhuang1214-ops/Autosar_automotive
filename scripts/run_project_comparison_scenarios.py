"""Run the public P18 project baseline/candidate comparison scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from automotive_workbench.project_comparison import (  # noqa: E402
    compare_project_reports,
)
from run_project_review_scenarios import run_scenarios  # noqa: E402


COMPARISONS = (
    ("stable", "baseline", "baseline", "stable"),
    ("scale-regression", "baseline", "scale-change", "regressed"),
    ("generation-regression", "baseline", "missing-init", "regressed"),
    ("generation-improvement", "missing-init", "baseline", "improved"),
)


def run_comparison_scenarios(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("P18 scenario output must be empty or absent")
    output = output.resolve()
    if not output.exists():
        output.mkdir(parents=True)

    review_scenarios = run_scenarios(output / "project-runs")
    comparisons = []
    for name, baseline, candidate, expected_status in COMPARISONS:
        project_root = output / "project-runs/projects"
        result = compare_project_reports(
            project_root / baseline / "bundle/project-report.json",
            project_root / candidate / "bundle/project-report.json",
            output / "comparisons" / name,
        )
        if (
            result["status"] != expected_status
            or result["evidence_validation"]["status"] != "passed"
        ):
            raise RuntimeError(
                f"{name}: expected {expected_status}/passed, got "
                f"{result['status']}/{result['evidence_validation']['status']}"
            )
        comparisons.append({
            "comparison": name,
            "baseline": baseline,
            "candidate": candidate,
            "status": result["status"],
            "evidence_validation": result["evidence_validation"]["status"],
            "summary": result["summary"],
        })

    summary = {
        "artifact_type": "project-comparison-scenario-result",
        "schema_version": "project-comparison-scenario-result-0.1",
        "status": "passed",
        "project_review_status": review_scenarios["status"],
        "comparisons": comparisons,
        "boundary": (
            "Regression describes declared report outcomes and finding deltas; it does "
            "not independently prove root cause or physical ECU behavior."
        ),
    }
    (output / "p18-project-comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_comparison_scenarios(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
