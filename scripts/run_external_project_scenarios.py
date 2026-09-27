"""Project 0.5 CLI gates, external diagnosis, review and portable comparison."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from run_external_ecu_scenarios import offline_build  # noqa: E402
from automotive_workbench.external_ecu import read_json, write_json  # noqa: E402
from automotive_workbench.evidence_bundle import verify_evidence_bundle  # noqa: E402
from automotive_workbench.project_review import run_project_review  # noqa: E402
from automotive_workbench.project_comparison import (  # noqa: E402
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.review import validate_citations  # noqa: E402


def prepare(source: Path, build_path: Path | None) -> tuple[dict, dict, dict]:
    source.mkdir(parents=True)
    project_path = ROOT / "examples/window_control/project-external.json"
    project = read_json(project_path)
    for key, value in list(project["inputs"].items()):
        if key == "execution":
            continue
        path = project_path.parent / value
        shutil.copyfile(path, source / path.name)
        project["inputs"][key] = path.name
    build_path = build_path.resolve() if build_path else offline_build(source)
    build = read_json(build_path)
    spec = {
        "schema_version": "external-ecu-execution-0.1",
        "build": str(build_path),
        "profile": "profile.json",
        "channel": build["bindings"]["channel"],
        "startup_delay_s": 1.0,
        "shutdown_timeout_s": 1.0,
        "launch_ecu": True,
        "fault": "none",
    }
    profile = read_json(ROOT / "examples/openbsw/read_cf01.json")
    project["inputs"]["execution"] = "execution.json"
    return project, spec, profile


def run(output: Path, build: Path | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Scenario output must be absent")
    output = output.resolve()
    project, spec, profile = prepare(output / "source", build)
    source = output / "source"
    contract_path = source / project["inputs"]["contract"]
    contract = contract_path.read_bytes()
    cases = [
        "baseline",
        "static-failure",
        "changed-definition",
        "binding-drift",
        "channel-drift",
    ]
    if build:
        cases += ["no-response", "wrong-did", "wrong-response-id"]
    results = {}
    for name in cases:
        candidate = json.loads(json.dumps(project))
        declaration, client = dict(spec), dict(profile)
        contract_path.write_bytes(contract)
        if name == "static-failure":
            value = read_json(contract_path)
            value["signals"][0]["resolution"] = "2"
            write_json(contract_path, value)
        if name == "changed-definition":
            candidate["requirements"][-1]["expected"] = "00"
        if name == "binding-drift":
            client["response_id"] += 1
        if name == "no-response":
            declaration["launch_ecu"] = False
        if name == "wrong-did":
            declaration["fault"], client["did"] = name, 0xCFFF
        if name == "wrong-response-id":
            declaration["fault"], client["response_id"] = (
                name,
                profile["response_id"] + 1,
            )
        write_json(source / "project.json", candidate)
        write_json(source / "execution.json", declaration)
        write_json(source / "profile.json", client)
        command = [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "run-project",
            str(source / "project.json"),
            "--interface",
            "socketcan",
            "--channel",
            "p23-wrong" if name == "channel-drift" else spec["channel"],
            "--output",
            str(output / name),
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        expected = (
            1
            if name in {"binding-drift", "channel-drift"}
            else 2
            if name == "static-failure" or (build and name != "baseline")
            else 0
            if build
            else 3
        )
        if completed.returncode != expected:
            raise ValueError(
                f"{name}: {completed.returncode}: {completed.stdout} {completed.stderr}"
            )
        if expected == 1:
            if (output / name).exists():
                raise ValueError("Invalid input created project output")
            results[name] = "rejected-before-output"
            continue
        path = output / name / "bundle/project-report.json"
        report = read_json(path)
        if name == "static-failure" and (
            report["stages"]["external_ecu"] != {"status": "skipped", "path": None}
            or (path.parent / "external-ecu").exists()
        ):
            raise ValueError("Static failure did not prevent ECU execution")
        if run_project_review(path, output / name / "review")["status"] != "answered":
            raise ValueError("Project review failed")
        results[name] = report["status"]
    baseline = output / "baseline/bundle/project-report.json"
    comparisons = {}
    for name in cases:
        if results[name] == "rejected-before-output":
            continue
        compared = compare_project_reports(
            baseline,
            output / name / "bundle/project-report.json",
            output / (name + "-compare"),
        )
        expected_comparison = (
            "stable"
            if name == "baseline"
            else "not-comparable"
            if name not in {"static-failure"}
            else "regressed"
            if build
            else "changed"
        )
        if compared["status"] != expected_comparison:
            raise ValueError(f"Unexpected comparison {name}: {compared['status']}")
        comparisons[name] = compared["status"]
    refused = run_project_review(
        baseline,
        output / "physical-claim",
        "This project proves successful operation on a physical production ECU.",
    )
    if refused["status"] != "refused":
        raise ValueError("Unsupported physical ECU claim was accepted")
    shutil.rmtree(source)  # Only this scenario's generated input copies.
    relocated = output.with_name(output.name + "-relocated")
    if relocated.exists():
        raise ValueError("Relocation destination exists")
    output.rename(relocated)
    verified = 0
    for name in comparisons:
        target = relocated / name
        check = verify_evidence_bundle(
            target / "bundle",
            target / "manifest.json",
            target / "relocated-verification",
            base=target,
        )
        if check["status"] != "passed":
            raise ValueError("Relocated manifest failed")
        if (
            validate_citations(
                target / "review/review-request.json",
                read_json(target / "review/review-result.json"),
            )["status"]
            != "passed"
        ):
            raise ValueError("Relocated citations failed")
        if (
            run_project_review(
                target / "bundle/project-report.json", target / "review-again"
            )["status"]
            != "answered"
        ):
            raise ValueError("Relocated review failed")
        validate_project_comparison(
            relocated / (name + "-compare") / "project-comparison.json"
        )
        verified += 1
    summary = {
        "status": "passed",
        "mode": "real-openbsw-socketcan" if build else "offline-blocked-only",
        "cases": results,
        "comparisons": comparisons,
        "relocated_verified": verified,
    }
    write_json(relocated / "summary.json", summary)
    relocated.rename(output)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    print(run(args.output, args.build))
