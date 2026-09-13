"""Run the public P17 project-review acceptance and refusal scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from automotive_workbench.can_io import BusConfig, sha256_file  # noqa: E402
from automotive_workbench.project_review import run_project_review  # noqa: E402
from automotive_workbench.project_workflow import run_project  # noqa: E402


CASES = {
    "baseline": "passed",
    "scale-change": "failed",
    "missing-init": "failed",
}


def run_scenarios(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("P17 scenario output must be empty or absent")
    output = output.resolve()
    if not output.exists():
        output.mkdir(parents=True)

    cases = []
    for name, expected_status in CASES.items():
        project = ROOT / "examples/generate_arxml/bridge" / name / "project.json"
        acceptance = run_project(
            project,
            output / "projects" / name,
            BusConfig("virtual", f"p17-project-review-{name}"),
        )
        if acceptance["status"] != expected_status:
            raise RuntimeError(
                f"{name}: expected project status {expected_status}, "
                f"got {acceptance['status']}"
            )
        report = Path(acceptance["report_json"])
        review = run_project_review(report, output / "reviews" / name)
        if review["status"] != "answered":
            raise RuntimeError(f"{name}: project review was not answered")
        cases.append({
            "case": name,
            "project_status": acceptance["status"],
            "review_status": review["status"],
            "review_coverage": review["coverage"],
            "citation_validation": review["citation_validation"]["status"],
            "project_report_sha256": sha256_file(report),
        })

    baseline_report = output / "projects/baseline/bundle/project-report.json"
    refusal = run_project_review(
        baseline_report,
        output / "reviews/physical-ecu-claim",
        "Physical ECU flash timing was measured and certified.",
    )
    refusal_codes = [item["code"] for item in refusal["refusal_reasons"]]
    if refusal["status"] != "refused" or "REVIEW-NO-EVIDENCE" not in refusal_codes:
        raise RuntimeError("Unsupported physical ECU claim was not refused")

    result = {
        "artifact_type": "project-review-scenario-result",
        "schema_version": "project-review-scenario-result-0.1",
        "status": "passed",
        "mode": "retrieval-only",
        "cases": cases,
        "unsupported_claim": {
            "status": refusal["status"],
            "reason_codes": refusal_codes,
            "citation_validation": refusal["citation_validation"]["status"],
        },
        "boundary": (
            "Public synthetic inputs and virtual CAN do not prove physical ECU or "
            "production behavior."
        ),
    }
    (output / "p17-project-review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_scenarios(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
