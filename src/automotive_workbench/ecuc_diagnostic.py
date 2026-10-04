"""Explicit ECUC acceptance dependencies on independently executed diagnostics.

A protected object is a prerequisite, never an inferred Dcm/generated-code mapping.
Saved evidence can be checked offline; the check is not ECU authentication.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json
import re
import uuid
import platform
from importlib.metadata import PackageNotFoundError, version

from automotive_workbench import __version__
from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.external_ecu import (
    _validate_documents,
    load_did_profile,
    read_json,
    write_json,
    validate_execution_context,
    verify_external_ecu,
)
from automotive_workbench.project_external import (
    capture_execution,
    execution_basis,
    run_project_external,
    same,
)
from automotive_workbench.ecuc_model import canonical
from automotive_workbench.ecuc_project import sha

VERSION = "ecuc-diagnostic-link-0.1"
BOUNDARY = "Explicit acceptance dependency only; no Dcm/CanTp or generated-code semantic mapping, physical ECU or target authentication."
ROLES = {
    "executable",
    "cache",
    "can_source",
    "docan_source",
    "uds_source",
    "configure_log",
    "build_log",
}
BASE_INPUTS = {
    "external-execution.json",
    "external-build.json",
    "external-profile.json",
    "runner-execution.json",
    "runner-build.json",
    "runner-profile.json",
}
IDENTITY = {
    "source_commit",
    "channel",
    "request_id",
    "response_id",
    "did",
    "expected_data_hex",
}


def declaration(value: Any, policies: set[str]) -> set[str]:
    if not isinstance(value, dict) or set(value) != {
        "id",
        "execution",
        "policy_ids",
        "relation",
        "identity",
    }:
        raise ValueError(
            "Diagnostic dependency requires closed id/execution/policy_ids/relation/identity"
        )
    if not isinstance(value["id"], str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", value["id"]
    ):
        raise ValueError("Invalid diagnostic dependency ID")
    if (
        not isinstance(value["execution"], str)
        or not value["execution"].strip()
        or "\0" in value["execution"]
    ):
        raise ValueError("Diagnostic execution path required")
    ids = value["policy_ids"]
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(x, str) or x not in policies for x in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError(
            "Diagnostic dependency must reference unique existing policies"
        )
    if value["relation"] not in ("acceptance-dependency", "configuration-semantic"):
        raise ValueError("Unknown diagnostic relation")
    identity = value["identity"]
    if not isinstance(identity, dict) or set(identity) != IDENTITY:
        raise ValueError("Diagnostic identity fields incomplete")
    for key, pattern in (
        ("source_commit", r"[a-f0-9]{40}"),
        ("channel", r"[A-Za-z0-9_.-]{1,15}"),
        ("expected_data_hex", r"(?:[A-Fa-f0-9]{2})+"),
    ):
        if not isinstance(identity[key], str) or not re.fullmatch(
            pattern, identity[key]
        ):
            raise ValueError("Invalid diagnostic identity: " + key)
    for key, maximum in (("request_id", 2047), ("response_id", 2047), ("did", 65535)):
        if type(identity[key]) is not int or not 0 <= identity[key] <= maximum:
            raise ValueError("Invalid diagnostic identity: " + key)
    if identity["request_id"] == identity["response_id"]:
        raise ValueError("Diagnostic CAN IDs must differ")
    return {value["id"]}


def capture(path: Path, project: dict) -> dict[str, bytes]:
    return {
        "inputs/" + k: v
        for k, v in capture_execution(
            path.parent / project["diagnostic"]["execution"]
        ).items()
    }


def input_inventory(bundle: Path) -> set[str]:
    names = BASE_INPUTS.copy()
    # Optional captured roles must match the original build hashes. Missing roles
    # remain explicit in the P23 blocked result and never invent executable bytes.
    for role in ROLES - {"executable"}:
        name = "external-" + role + ".txt"
        if (bundle / "inputs" / name).exists():
            names.add(name)
    return names


def inputs(bundle: Path) -> dict[str, bytes]:
    snapshots = {
        name: (bundle / "inputs" / name).read_bytes()
        for name in input_inventory(bundle)
    }
    original, runner = (
        json.loads(snapshots[n])
        for n in ("external-execution.json", "runner-execution.json")
    )
    build, normalized = (
        json.loads(snapshots[n]) for n in ("external-build.json", "runner-build.json")
    )
    profile, _ = load_did_profile(bundle / "inputs/external-profile.json")
    _validate_documents(original, build, profile)
    if (
        not same(
            runner,
            {
                **original,
                "build": "runner-build.json",
                "profile": "runner-profile.json",
            },
        )
        or snapshots["external-profile.json"] != snapshots["runner-profile.json"]
    ):
        raise ValueError("Diagnostic execution snapshot drift")

    def without_paths(value: dict) -> dict:
        return {
            **value,
            "files": [
                {k: v for k, v in item.items() if k != "path"}
                for item in value["files"]
            ],
        }

    if not same(without_paths(build), without_paths(normalized)):
        raise ValueError("Diagnostic build snapshot drift")
    if (
        len(build["files"]) != len(ROLES)
        or {x["role"] for x in build["files"]} != ROLES
    ):
        raise ValueError("Diagnostic build roles incomplete")
    for item in build["files"]:
        if (
            set(item) != {"role", "path", "sha256"}
            or not isinstance(item["path"], str)
            or not item["path"]
            or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
        ):
            raise ValueError("Invalid diagnostic build file")
        data = snapshots.get("external-" + item["role"] + ".txt")
        if data is not None and sha(data) != item["sha256"]:
            raise ValueError("Diagnostic source hash mismatch")
    return snapshots


def preflight(
    project: dict, static: dict, snapshots: dict[str, bytes], config: dict
) -> dict:
    definition = project["diagnostic"]
    build = json.loads(snapshots["external-build.json"])
    spec = json.loads(snapshots["external-execution.json"])
    if (
        set(config) != {"interface", "channel", "receive_own_messages", "fd"}
        or not all(
            isinstance(config[k], str) and config[k] for k in ("interface", "channel")
        )
        or any(type(config[k]) is not bool for k in ("fd", "receive_own_messages"))
    ):
        raise ValueError("Invalid diagnostic backend declaration")
    if static["status"] != "passed":
        return {"status": "blocked", "reason": "static_acceptance_rejected"}
    if definition["relation"] != "acceptance-dependency":
        return {
            "status": "unassessed",
            "reason": "configuration_semantic_provenance_missing",
        }
    identity = {"source_commit": build["source_commit"], **build["bindings"]}
    if not same(definition["identity"], identity):
        return {"status": "unassessed", "reason": "diagnostic_identity_mismatch"}
    if not same(config, asdict(BusConfig("socketcan", spec["channel"]))):
        return {"status": "blocked", "reason": "diagnostic_backend_mismatch"}
    return {"status": "passed", "reason": "explicit_acceptance_dependency"}


def context(bundle: Path, snapshots: dict[str, bytes], run_id: str) -> dict:
    project = read_json(bundle / "inputs/project.json")
    return {
        "run_id": run_id,
        "project_sha256": sha256_file(bundle / "inputs/project.json"),
        "baseline_sha256": sha256_file(bundle / "ecuc/before/ecuc-review.json"),
        "candidate_sha256": sha256_file(bundle / "ecuc/after/ecuc-review.json"),
        "policy_sha256": sha(canonical(project["policies"]).encode()),
        "execution_basis": execution_basis(snapshots),
    }


def producer() -> dict:
    versions: dict[str, str | None] = {}
    for package in ("python-can", "cantools", "can-isotp", "udsoncan"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "workbench_version": __version__,
        "python": platform.python_version(),
        "dependencies": versions,
    }


def execute(bundle: Path, project: dict, static: dict, config: BusConfig) -> None:
    snapshots = inputs(bundle)
    conditions = asdict(config)
    gate = preflight(project, static, snapshots, conditions)
    ctx = context(bundle, snapshots, uuid.uuid4().hex)
    runtime_path, digest = "", ""
    if gate["status"] == "passed":
        run_project_external(bundle / "inputs", bundle, execution_context=ctx)
        runtime_path = "external-ecu/external-ecu-report.json"
        digest = sha256_file(bundle / runtime_path)
    write_json(
        bundle / "diagnostic-link.json",
        {
            "schema_version": VERSION,
            "context": ctx,
            "requested_config": conditions,
            "preflight": gate,
            "runtime_path": runtime_path,
            "runtime_sha256": digest,
            "boundary": BOUNDARY,
            "producer": producer(),
        },
    )


def replay(bundle: Path, project: dict, static: dict) -> dict:
    snapshots = inputs(bundle)
    record = read_json(bundle / "diagnostic-link.json")
    if (
        set(record)
        != {
            "schema_version",
            "context",
            "requested_config",
            "preflight",
            "runtime_path",
            "runtime_sha256",
            "boundary",
            "producer",
        }
        or record["schema_version"] != VERSION
        or record["boundary"] != BOUNDARY
    ):
        raise ValueError("Invalid diagnostic link record")
    if (
        not isinstance(record["producer"], dict)
        or set(record["producer"]) != {"workbench_version", "python", "dependencies"}
        or not isinstance(record["producer"]["workbench_version"], str)
        or not record["producer"]["workbench_version"]
    ):
        raise ValueError("Invalid diagnostic producer")
    versions = record["producer"]["dependencies"]
    if (
        not isinstance(record["producer"]["python"], str)
        or not record["producer"]["python"]
        or not isinstance(versions, dict)
        or set(versions) != {"python-can", "cantools", "can-isotp", "udsoncan"}
        or any(
            v is not None and (not isinstance(v, str) or not v)
            for v in versions.values()
        )
    ):
        raise ValueError("Invalid diagnostic tool versions")
    validate_execution_context(record["context"])
    expected_context = context(bundle, snapshots, record["context"]["run_id"])
    if not same(record["context"], expected_context):
        raise ValueError("Diagnostic execution context mismatch")
    gate = preflight(project, static, snapshots, record["requested_config"])
    if not same(gate, record["preflight"]):
        raise ValueError("Diagnostic preflight differs from replay")
    status, reason = gate["status"], gate["reason"]
    runtime_pointer = ""
    if status == "passed":
        path = bundle / "external-ecu/external-ecu-report.json"
        if (
            record["runtime_path"] != "external-ecu/external-ecu-report.json"
            or sha256_file(path) != record["runtime_sha256"]
        ):
            raise ValueError("Diagnostic runtime missing or hash mismatch")
        verify_external_ecu(path)
        raw = read_json(path)
        if raw["schema_version"] != "external-ecu-run-0.2" or not same(
            raw["execution_context"], expected_context
        ):
            raise ValueError("Diagnostic runtime context mismatch")
        for role in ("execution", "build", "profile"):
            if (path.parent / f"inputs/{role}.json").read_bytes() != snapshots[
                f"runner-{role}.json"
            ]:
                raise ValueError("Diagnostic runtime input drift")
        # P23 validates the captured build roles, process cleanup and diagnostic
        # outcome. Bind its source snapshots to the configuration project's copies.
        for name, data in snapshots.items():
            if name.startswith("external-") and name.endswith(".txt"):
                if (
                    path.parent / "inputs" / name.removeprefix("external-")
                ).read_bytes() != data:
                    raise ValueError("Diagnostic runtime source drift")
        status, reason = raw["status"], raw["reason"] or "independent_diagnostic_passed"
        runtime_pointer = "/status"
    elif (
        record["runtime_path"] != ""
        or record["runtime_sha256"] != ""
        or (bundle / "external-ecu").exists()
    ):
        raise ValueError("Rejected diagnostic gate contains runtime evidence")
    definition = project["diagnostic"]
    return {
        "diagnostic." + definition["id"]: {
            "status": status,
            "reason": reason,
            "evidence": {"path": "diagnostic-link.json", "pointer": "/context"},
            "affected_objects": sorted(
                {
                    p["object_id"]
                    for p in project["policies"]
                    if p["id"] in definition["policy_ids"]
                }
            ),
            "binding": {
                k: v
                for k, v in definition.items()
                if k not in {"execution", "identity"}
            }
            | definition["identity"],
            "run_id": record["context"]["run_id"],
            "runtime_path": record["runtime_path"],
            "runtime_pointer": runtime_pointer,
            "witness_pointers": [
                "/checks/policy." + p + "/status" for p in definition["policy_ids"]
            ],
        }
    }


def comparison_basis(project: dict, bundle: Path) -> str:
    record = read_json(bundle / "diagnostic-link.json")
    return sha(
        canonical(
            {
                "declaration": {
                    k: v for k, v in project["diagnostic"].items() if k != "execution"
                },
                "execution_basis": execution_basis(inputs(bundle)),
                "backend": record["requested_config"],
            }
        ).encode()
    )
