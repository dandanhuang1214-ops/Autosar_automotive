from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_REJECTION_NAME = "review-evaluation-rejection.json"
_SUMMARY_NAME = "review-rejection-exercise.json"


def prepare_manifest(source: Path, destination: Path) -> None:
    manifest = json.loads(source.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Rejection exercise requires at least one evaluation case")

    for case in cases:
        request = case.get("request")
        if isinstance(request, str):
            case["request"] = str((source.parent / request).resolve())
        for report in case.get("external_reports", []):
            report_source = report.get("source")
            if isinstance(report_source, str):
                report["source"] = str((source.parent / report_source).resolve())

    reports = cases[0].get("external_reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("Rejection exercise requires an external report")
    reports[0]["expected_sha256"] = "0" * 64

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check_rejection(output: Path, cli_outcome: str) -> dict[str, Any]:
    if cli_outcome != "failure":
        raise ValueError(
            f"Controlled rejection CLI outcome must be failure, got {cli_outcome!r}"
        )

    rejection_path = output / _REJECTION_NAME
    rejection = json.loads(rejection_path.read_text(encoding="utf-8"))
    expected_keys = {
        "artifact_type", "schema_version", "run_id", "started_at",
        "evaluation_id", "case_id", "status", "phase", "reason",
    }
    if set(rejection) != expected_keys:
        raise ValueError("Controlled rejection artifact has unexpected fields")
    if rejection["artifact_type"] != "engineering-review-evaluation-rejection":
        raise ValueError("Controlled rejection artifact type is invalid")
    if rejection["schema_version"] != "review-evaluation-rejection-1.0":
        raise ValueError("Controlled rejection schema version is invalid")
    if rejection["status"] != "rejected":
        raise ValueError("Controlled rejection status is invalid")
    if rejection["phase"] != "external-report-preflight":
        raise ValueError("Controlled rejection phase is invalid")
    if rejection["reason"] != {
        "code": "sha256-mismatch",
        "stage": "integrity",
        "report_index": 1,
    }:
        raise ValueError("Controlled rejection reason is invalid")

    forbidden = (
        "materialized-request", "external_reports", "expected_sha256",
        "ci_provenance", "provenance_expectation", "provenance_policy",
    )
    serialized = json.dumps(rejection)
    leaked = [field for field in forbidden if field in serialized]
    if leaked:
        raise ValueError(f"Controlled rejection leaked forbidden fields: {leaked}")
    if (output / "review-evaluation.json").exists():
        raise ValueError("Controlled rejection unexpectedly produced an evaluation result")
    if any(output.rglob("materialized-request.json")):
        raise ValueError("Controlled rejection unexpectedly materialized a review request")

    summary = {
        "artifact_type": "engineering-review-rejection-exercise",
        "schema_version": "review-rejection-exercise-1.0",
        "status": "passed",
        "cli_outcome": cli_outcome,
        "rejection_artifact": _REJECTION_NAME,
        "reason_code": rejection["reason"]["code"],
        "materialized_request_absent": True,
        "evaluation_result_absent": True,
    }
    (output / _SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare or verify the controlled review rejection CI exercise"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("destination", type=Path)
    check = subparsers.add_parser("check")
    check.add_argument("output", type=Path)
    check.add_argument("--cli-outcome", required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        prepare_manifest(args.source, args.destination)
    else:
        summary = check_rejection(args.output, args.cli_outcome)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
