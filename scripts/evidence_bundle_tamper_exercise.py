from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


TAMPERED_PATH = "runtime/can-runtime-report.json"
VERIFICATION_KEYS = {
    "artifact_type", "schema_version", "bundle_id", "verified_at", "manifest_sha256",
    "status", "expected_artifact_count", "actual_artifact_count",
    "verified_artifact_count", "dependency_count", "verified_dependency_count",
    "finding_count", "findings",
}


def prepare_tampered_bundle(source: Path, destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise ValueError(f"Tampered bundle destination already exists: {destination}")
    shutil.copytree(source, destination)
    target = destination / TAMPERED_PATH
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"Controlled tamper target is not a regular file: {target}")
    with target.open("ab") as stream:
        stream.write(b"\n")
    return {
        "status": "prepared",
        "tampered_path": TAMPERED_PATH,
        "mutation": "append-newline",
    }


def check_tamper_rejection(output: Path, cli_outcome: str) -> dict[str, Any]:
    if cli_outcome != "failure":
        raise ValueError("Controlled verify-evidence CLI outcome must be failure")
    report_path = output / "evidence-bundle-verification.json"
    if not report_path.is_file():
        raise ValueError("Controlled tamper verification report is missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or set(report) != VERIFICATION_KEYS:
        raise ValueError("Controlled tamper verification must use the closed result schema")
    if report.get("status") != "failed":
        raise ValueError("Controlled tamper verification must have failed status")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Controlled tamper verification findings are missing")
    matched = next(
        (
            finding
            for finding in findings
            if isinstance(finding, dict)
            and finding.get("code") == "EVIDENCE-SIZE-MISMATCH"
            and finding.get("path") == TAMPERED_PATH
        ),
        None,
    )
    if matched is None:
        raise ValueError("Controlled tamper size mismatch finding is missing")
    summary = {
        "artifact_type": "evidence-bundle-tamper-exercise",
        "schema_version": "evidence-bundle-tamper-exercise-0.1",
        "status": "passed",
        "cli_outcome": cli_outcome,
        "reason_code": matched["code"],
        "tampered_path": TAMPERED_PATH,
        "verification_status": report["status"],
    }
    (output / "evidence-bundle-tamper-exercise.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("destination", type=Path)
    check = commands.add_parser("check")
    check.add_argument("output", type=Path)
    check.add_argument("--cli-outcome", required=True)
    args = parser.parse_args()
    try:
        result = (
            prepare_tampered_bundle(args.source, args.destination)
            if args.command == "prepare"
            else check_tamper_rejection(args.output, args.cli_outcome)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
