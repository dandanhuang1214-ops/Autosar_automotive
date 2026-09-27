"""Version 0.5 project integration; external ECU evidence has its own scope."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.external_ecu import (
    load_execution,
    read_json,
    run_external_ecu,
    verify_external_ecu,
    write_json,
)

BOUNDARY = "Independent POSIX ECU diagnostic evidence; no inferred mapping from project DBC/SWC to OpenBSW internals or physical ECU."


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def same(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def capture_execution(path: Path) -> dict[str, bytes]:
    spec, build, _, snapshots, _ = load_execution(path)
    result = {"external-" + name: data for name, data in snapshots.items()}
    normalized = json.loads(json.dumps(build))
    base = (path.parent / spec["build"]).parent
    for item in normalized["files"]:
        item["path"] = str((base / item["path"]).resolve())
    result["runner-build.json"] = encoded(normalized)
    result["runner-profile.json"] = snapshots["profile.json"]
    result["runner-execution.json"] = encoded(
        {**spec, "build": "runner-build.json", "profile": "runner-profile.json"}
    )
    return result


def execution_basis(snapshots: dict[str, bytes]) -> str:
    spec = json.loads(snapshots["external-execution.json"])
    build = json.loads(snapshots["external-build.json"])
    profile = json.loads(snapshots["external-profile.json"])
    semantic = {
        "spec": {k: v for k, v in spec.items() if k not in {"build", "profile"}},
        "build": {k: v for k, v in build.items() if k != "files"},
        "files": sorted(
            ({"role": x["role"], "sha256": x["sha256"]} for x in build["files"]),
            key=lambda x: x["role"],
        ),
        "profile": profile,
    }
    return hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()


def validate_backend(snapshots: dict[str, bytes], config: BusConfig) -> None:
    spec = json.loads(snapshots["external-execution.json"])
    if (
        config.interface != "socketcan"
        or config.channel != spec["channel"]
        or config.fd
        or config.receive_own_messages
    ):
        raise ValueError(
            "Project 0.5 requires explicit classic SocketCAN matching the external ECU channel"
        )


def summarize_execution(root: Path) -> dict:
    path = root / "external-ecu-report.json"
    verify_external_ecu(path)
    report = read_json(path)
    diagnostic = (
        read_json(root / report["diagnostic"]) if report["diagnostic"] else None
    )
    return {
        "artifact_type": "external-ecu-project-stage",
        "schema_version": "external-ecu-project-stage-0.1",
        "status": report["status"],
        "reason": report["reason"],
        "execution": "external-ecu/external-ecu-report.json",
        "execution_sha256": sha256_file(path),
        "source_commit": report["source_commit"],
        "launch_ecu": report["launch_ecu"],
        "diagnostic": {
            key: diagnostic[key]
            for key in (
                "status",
                "reason",
                "request_payload_hex",
                "response_payload_hex",
                "expected_data_hex",
                "actual_data_hex",
                "negative_response_code",
            )
        }
        if diagnostic
        else None,
        "boundary": BOUNDARY,
    }


def portable_static(report: dict) -> dict:
    for key in ("dbc", "contract", "intent"):
        if key in report:
            report[key] = "inputs/" + Path(report[key]).name
    for finding in report.get("findings", []):
        if finding.get("source_artifact"):
            finding["source_artifact"] = (
                "inputs/" + Path(finding["source_artifact"]).name
            )
    return report


def run_project_external(inputs: Path, bundle: Path) -> dict:
    output = bundle / "external-ecu"
    run_external_ecu(inputs / "runner-execution.json", output)
    # Manifest sources resolve against the project portable base, not the JSON's directory.
    path = output / "diagnostic/uds-did-report.json"
    if path.is_file():
        diagnostic = read_json(path)
        diagnostic["profile"]["source"] = "bundle/external-ecu/inputs/profile.json"
        if diagnostic["capture"]:
            diagnostic["capture"]["source"] = (
                "bundle/external-ecu/diagnostic/uds-did.log"
            )
        diagnostic["source_artifacts"] = [diagnostic["profile"]] + (
            [diagnostic["capture"]] if diagnostic["capture"] else []
        )
        write_json(path, diagnostic)
        report_path = output / "external-ecu-report.json"
        report = read_json(report_path)
        for item in report["inventory"]:
            item["sha256"] = sha256_file(output / item["path"])
        write_json(report_path, report)
    return summarize_execution(output)


def validate_project_external(
    root: Path, report: dict, snapshots: dict[str, bytes]
) -> None:
    """Recompute stage and acceptance facts without opening a bus or launching anything."""
    from automotive_workbench.adapters.canonical_contract import (
        validate_contract_mapping,
    )
    from automotive_workbench.adapters.dbc import validate_dbc_intent
    from automotive_workbench.project_workflow import evaluate_requirements

    inputs = root / "inputs"
    original_spec = json.loads(snapshots["external-execution.json"])
    runner_spec = json.loads(snapshots["runner-execution.json"])
    if (
        runner_spec
        != {
            **original_spec,
            "build": "runner-build.json",
            "profile": "runner-profile.json",
        }
        or snapshots["runner-profile.json"] != snapshots["external-profile.json"]
    ):
        raise ValueError("External execution snapshot binding mismatch")
    original_build, runner_build = (
        json.loads(snapshots[key])
        for key in ("external-build.json", "runner-build.json")
    )

    def without_paths(build: dict) -> dict:
        return {
            **build,
            "files": [
                {k: v for k, v in item.items() if k != "path"}
                for item in build["files"]
            ],
        }

    if not same(without_paths(original_build), without_paths(runner_build)):
        raise ValueError("External build snapshot binding mismatch")
    expected_static = {
        "canonical": validate_contract_mapping(
            inputs / "dbc.dbc", inputs / "contract.json", inputs / "intent.json"
        ),
        "mapping": validate_dbc_intent(inputs / "dbc.dbc", inputs / "intent.json"),
    }
    from automotive_workbench.external_ecu import _validate_documents
    from automotive_workbench.uds_client import load_did_profile

    profile, _ = load_did_profile(inputs / "external-profile.json")
    _validate_documents(original_spec, original_build, profile)
    if len(original_build["files"]) != 7 or {
        item["role"] for item in original_build["files"]
    } != {
        "executable",
        "cache",
        "can_source",
        "docan_source",
        "uds_source",
        "configure_log",
        "build_log",
    }:
        raise ValueError("Incomplete external build snapshot roles")
    for item in original_build["files"]:
        captured = snapshots.get("external-" + item["role"] + ".txt")
        if (
            captured is not None
            and hashlib.sha256(captured).hexdigest() != item["sha256"]
        ):
            raise ValueError("External build source snapshot mismatch")
    project_definition = json.loads(snapshots["project.json"])
    if report["name"] != project_definition["name"]:
        raise ValueError("Project name disagrees with snapshot")
    stage_paths = {
        "canonical": "canonical.json",
        "mapping": "mapping.json",
        "arxml": "arxml.json",
        "communication": "communication/bound-communication.json",
        "external_ecu": "external-ecu.json",
    }
    if "generation" in project_definition:
        stage_paths["generation"] = "generation.json"
    if set(report["stages"]) != set(stage_paths):
        raise ValueError("Project stage set disagrees with definition")
    for name, declaration in report["stages"].items():
        if set(declaration) != {"status", "path"} or (
            declaration["path"] is not None and declaration["path"] != stage_paths[name]
        ):
            raise ValueError("Invalid fixed project stage path")
    stage_reports = {}
    paths = {}
    for stage, declaration in report["stages"].items():
        if declaration["path"]:
            paths[stage] = declaration["path"]
            stage_reports[stage] = read_json(root / declaration["path"])
            if declaration["status"] != stage_reports[stage]["status"]:
                raise ValueError("Project stage status mismatch")
    for stage, expected in expected_static.items():
        if not same(stage_reports.get(stage), portable_static(expected)):
            raise ValueError("Static report disagrees with snapshots")
    project = json.loads(snapshots["project.json"])
    if "generation" in project:
        from automotive_workbench.adapters.generation_gate import load_generation

        declaration = {
            **project["generation"],
            "source_docx": "source.docx",
            "issue_report": "generation-issues.json",
        }
        _, gate = load_generation(declaration, inputs, snapshots["contract.json"])
        saved = {
            key: value
            for key, value in stage_reports.get("generation", {}).items()
            if key != "source_artifacts"
        }
        if not same(saved, gate):
            raise ValueError("Generation gate disagrees with snapshots")
    static_passed = all(
        stage_reports[name]["status"] == "passed"
        for name in ("canonical", "mapping", "arxml")
    )
    if "generation" in stage_reports:
        static_passed = (
            static_passed and stage_reports["generation"]["status"] == "passed"
        )
    if static_passed:
        if report["stages"].get("external_ecu", {}).get("path") != "external-ecu.json":
            raise ValueError("Missing external ECU project stage")
        for name in ("execution", "build", "profile"):
            if (
                root / "external-ecu/inputs" / (name + ".json")
            ).read_bytes() != snapshots["runner-" + name + ".json"]:
                raise ValueError("Runtime and project snapshots disagree")
        if not same(
            stage_reports["external_ecu"], summarize_execution(root / "external-ecu")
        ):
            raise ValueError("External stage disagrees with actual execution evidence")
        from automotive_workbench.project_declared import bind_declared_paths

        runtime = read_json(root / "communication/runtime/declared-runtime-report.json")
        expected_binding = bind_declared_paths(stage_reports["mapping"], runtime)
        saved_binding = {
            key: value
            for key, value in stage_reports["communication"].items()
            if key != "source_artifacts"
        }
        if not same(expected_binding, saved_binding):
            raise ValueError("Communication binding disagrees with runtime")
    elif (
        report["stages"].get("communication") != {"status": "skipped", "path": None}
        or report["stages"].get("external_ecu") != {"status": "skipped", "path": None}
        or (root / "external-ecu").exists()
        or (root / "communication").exists()
    ):
        raise ValueError("Static failure must skip external execution")
    project = json.loads(snapshots["project.json"])
    requirements, status = evaluate_requirements(
        project, stage_reports, paths, report["stages"], root
    )
    if not same(requirements, report["requirements"]) or status != report["status"]:
        raise ValueError("Project acceptance disagrees with stage evidence")
