from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


VERIFICATION_KEYS = {
    "artifact_type", "schema_version", "bundle_id", "verified_at",
    "capsule_report_sha256", "manifest_sha256", "source_delivery_status",
    "status", "expected_file_count", "actual_file_count", "verified_file_count",
    "artifact_count", "verified_artifact_count", "dependency_count",
    "verified_dependency_count", "finding_count", "findings",
}


def prepare(source: Path, target: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Source capsule must be a regular directory")
    if target.exists() or target.is_symlink():
        raise ValueError("Controlled tamper target must not already exist")
    shutil.copytree(source, target)
    relative = "communication-evidence-delivery.json"
    tampered = target / relative
    with tampered.open("ab") as stream:
        stream.write(b"\n")
    return {"status": "prepared", "tampered_path": relative}


def check(output: Path, cli_outcome: str) -> dict[str, Any]:
    if cli_outcome != "failure":
        raise ValueError("Controlled capsule tamper CLI outcome must be failure")
    verification_path = output / "evidence-capsule-verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if not isinstance(verification, dict) or set(verification) != VERIFICATION_KEYS:
        raise ValueError("Controlled capsule tamper verification must use the closed schema")
    if verification["artifact_type"] != "evidence-capsule-verification":
        raise ValueError("Controlled capsule tamper artifact type is invalid")
    if verification["schema_version"] != "evidence-capsule-verification-0.1":
        raise ValueError("Controlled capsule tamper schema version is invalid")
    if verification["status"] != "failed":
        raise ValueError("Controlled capsule tamper verification must fail")
    matching = [
        item for item in verification["findings"]
        if item.get("code") == "CAPSULE-SHA256-MISMATCH"
        and item.get("path") == "communication-evidence-delivery.json"
    ]
    if len(matching) != 1:
        raise ValueError("Controlled capsule tamper finding is missing or duplicated")
    result = {
        "artifact_type": "evidence-capsule-tamper-exercise",
        "schema_version": "evidence-capsule-tamper-exercise-0.1",
        "status": "passed",
        "cli_outcome": cli_outcome,
        "verification_status": verification["status"],
        "tampered_path": "communication-evidence-delivery.json",
        "finding_code": "CAPSULE-SHA256-MISMATCH",
    }
    (output / "evidence-capsule-tamper-exercise.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("source", type=Path)
    prepare_parser.add_argument("target", type=Path)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("output", type=Path)
    check_parser.add_argument("--cli-outcome", required=True)
    args = parser.parse_args()
    try:
        result = (
            prepare(args.source, args.target)
            if args.command == "prepare"
            else check(args.output, args.cli_outcome)
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
