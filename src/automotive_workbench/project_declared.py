"""P20 project snapshot preflight, identity binding and portable source validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _cantools
from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.communication_plan import compile_plan, parse_declaration
from automotive_workbench.declared_communication import run_declared_communication


def prepare_declared_project(
    project: dict[str, Any], snapshots: dict[str, bytes]
) -> dict[str, Any]:
    key = project.get("comparison_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
        raise ValueError("Project comparison_key must be a portable identifier")
    declaration = parse_declaration(snapshots["vectors.json"])
    intent = json.loads(snapshots["intent.json"].decode("utf-8-sig"))
    database = _cantools().database.load_string(
        snapshots["dbc.dbc"].decode("cp1252"), database_format="dbc"
    )
    compile_plan(database, intent, declaration)
    identities = set()
    for signal in intent["signals"]:
        identity = (signal["dbc_message"], signal["dbc_signal"])
        if identity in identities:
            raise ValueError("Mapped signal identity must be unique")
        identities.add(identity)
        if not any(
            v["message"] == identity[0]
            and identity[1] in v["signals"]
            and v["direction"] == signal["direction"]
            for v in declaration["vectors"]
        ):
            raise ValueError(f"Mapped path has no declared vector: {identity}")
    if not identities:
        raise ValueError("Declared projects require mapped communication paths")
    return {
        "key": key,
        "local_ecu": intent["local_ecu"],
        "vectors": sorted(declaration["vectors"], key=lambda v: v["id"]),
    }


def bind_declared_paths(
    mapping: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    bindings: dict[str, Any] = {}
    findings = []
    for vector in runtime["plan"]["vectors"]:
        vector_id = vector["id"]
        actual = runtime["vectors"].get(vector_id)
        bindings[vector_id] = {}
        for path in mapping["communication_paths"]:
            if path["dbc_message"] != vector["message"]:
                continue
            signal = path["dbc_signal"]
            reason = ""
            observation = actual.get("observed") if actual else None
            identity_ok = (
                actual is not None
                and actual["id"] == vector_id
                and actual["message"] == path["dbc_message"]
                and actual["direction"] == path["direction"] == vector["direction"]
                and vector["frame_id"] == path["frame_id"]
                and signal in vector["expected_raw_signals"]
            )
            if not identity_ok:
                reason = "identity_mismatch"
            elif actual["status"] == "blocked":
                reason = "backend_unavailable"
            elif actual["status"] != "passed":
                reason = actual["reason"] or "vector_failed"
            elif (
                not observation
                or observation["frame_id"] != path["frame_id"]
                or observation["is_extended_id"] != vector["is_extended_id"]
                or (observation.get("raw_signals") or {}).get(signal)
                != vector["expected_raw_signals"][signal]
            ):
                reason = "observation_mismatch"
            status = (
                "blocked"
                if reason == "backend_unavailable"
                else "failed"
                if reason
                else "passed"
            )
            bindings[vector_id][signal] = {
                "status": status,
                "reason": reason,
                "path": path,
                "runtime_pointer": "/vectors/" + vector_id,
                "raw_value": (observation.get("raw_signals") or {}).get(signal)
                if observation
                else None,
            }
            if status == "failed":
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "DECLARED-PATH-FAILED",
                        "message": f"{vector_id}: {path['dbc_message']}.{signal}: {reason}",
                    }
                )
    covered = {
        (entry["path"]["dbc_message"], entry["path"]["dbc_signal"])
        for group in bindings.values()
        for entry in group.values()
    }
    for path in mapping["communication_paths"]:
        if (path["dbc_message"], path["dbc_signal"]) not in covered:
            findings.append(
                {
                    "severity": "ERROR",
                    "code": "DECLARED-PATH-MISSING",
                    "message": f"{path['dbc_message']}.{path['dbc_signal']}: no vector",
                }
            )
    return {
        "artifact_type": "declared-communication-binding",
        "schema_version": "declared-communication-binding-0.1",
        "status": "failed"
        if findings or runtime["status"] == "failed"
        else runtime["status"],
        "bindings": bindings,
        "vectors": runtime["vectors"],
        "bound_count": sum(
            e["status"] == "passed" for g in bindings.values() for e in g.values()
        ),
        "path_count": len(mapping["communication_paths"]),
        "finding_count": len(findings),
        "findings": findings,
    }


def run_bound_communication(
    dbc: Path,
    intent: Path,
    declaration: Path,
    mapping: dict[str, Any],
    config: BusConfig,
    output: Path,
) -> dict[str, Any]:
    runtime = run_declared_communication(
        dbc, intent, declaration, config, output / "runtime"
    )
    result = bind_declared_paths(mapping, runtime)
    result["source_artifacts"] = [
        {"source": str(path), "sha256": sha256_file(path)}
        for path in [
            dbc,
            intent,
            declaration,
            output / "runtime/declared-runtime-report.json",
        ]
    ]
    (output / "bound-communication.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def validate_declared_sources(report_path: Path, report: dict[str, Any]) -> None:
    """Validate 0.3 snapshot provenance after relocation, without writing anything."""
    if report["schema_version"] != "project-acceptance-0.3":
        return
    root = report_path.parent.resolve()
    sources = report.get("source_artifacts", [])
    seen = set()
    for item in sources:
        name = item["source"]
        relative = Path(name)
        if relative.is_absolute() or not name.startswith("bundle/") or "\\" in name:
            raise ValueError("Invalid portable project source")
        path = (root.parent / relative).resolve()
        if (
            not path.is_relative_to(root)
            or path == report_path.resolve()
            or name in seen
        ):
            raise ValueError("Unsafe or duplicate project source")
        seen.add(name)
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Project source missing or modified: {name}")
    required = {
        "bundle/inputs/" + name
        for name in [
            "project.json",
            "dbc.dbc",
            "intent.json",
            "contract.json",
            "vectors.json",
        ]
    }
    required.update(
        "bundle/" + stage["path"]
        for stage in report["stages"].values()
        if stage["path"]
    )
    if not required <= seen:
        raise ValueError("Project source inventory is incomplete")
    if (
        report["stages"]["communication"]["path"]
        and "bundle/communication/runtime/declared-runtime-report.json" not in seen
    ):
        raise ValueError("Runtime source is missing from inventory")
    snapshots = {
        p.name: p.read_bytes() for p in (root / "inputs").iterdir() if p.is_file()
    }
    project = json.loads(snapshots["project.json"].decode("utf-8-sig"))
    expected = prepare_declared_project(project, snapshots)

    # JSON canonical bytes distinguish true from 1 and preserve full definitions.
    def canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, allow_nan=False)

    if canonical(report.get("comparison_basis")) != canonical(expected):
        raise ValueError("Comparison basis disagrees with project snapshot")
    definitions = [
        {key: item[key] for key in ["id", "text", "stage", "pointer", "expected"]}
        for item in report["requirements"]
    ]
    if canonical(definitions) != canonical(project["requirements"]):
        raise ValueError("Requirement definitions disagree with project snapshot")
