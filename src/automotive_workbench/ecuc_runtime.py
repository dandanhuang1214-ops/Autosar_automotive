"""Explicit ECUC-to-CAN evidence links; no generated-code equivalence inferred."""

from __future__ import annotations

import json
import re
import tempfile
import uuid
import platform
from importlib.metadata import version

from automotive_workbench import __version__
from dataclasses import asdict
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.dbc import _load_dbc
from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.communication_plan import preflight_communication
from automotive_workbench.declared_communication import run_declared_communication
from automotive_workbench.ecuc_model import canonical
from automotive_workbench.ecuc_project import sha

FILES = {
    "dbc": "runtime.dbc",
    "intent": "runtime-intent.json",
    "vectors": "runtime-vectors.json",
}
VERSION = "ecuc-runtime-link-0.1"
BOUNDARY = "Explicit synthetic ECUC/DBC association and two local CAN endpoints; not vendor-generated BSW, independent ECU, timing or physical ECU validation."


def same(left: Any, right: Any) -> bool:
    return canonical(left) == canonical(right)


def declaration(value: Any, policies: list[dict]) -> set[str]:
    if not isinstance(value, dict) or set(value) != {"inputs", "bindings"}:
        raise ValueError("Runtime links require closed inputs and bindings")
    inputs = value["inputs"]
    if (
        not isinstance(inputs, dict)
        or set(inputs) != set(FILES)
        or any(not isinstance(v, str) or not v.strip() for v in inputs.values())
    ):
        raise ValueError("Runtime inputs require dbc, intent and vectors paths")
    rows = value["bindings"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        raise ValueError("Declare 1..256 runtime bindings")
    ids: set[str] = set()
    known = {p["id"] for p in policies}
    fields = {
        "id",
        "policy_ids",
        "object_id",
        "com_ipdu",
        "route",
        "canif_pdu",
        "vector_id",
        "message",
        "signal",
        "direction",
        "frame_id",
    }
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Runtime binding fields differ from contract")
        for key in fields - {"frame_id", "policy_ids"}:
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError("Runtime binding names must be nonempty strings")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", row["id"]) or row["id"] in ids:
            raise ValueError("Runtime binding IDs must be unique portable identifiers")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", row["vector_id"]):
            raise ValueError("Runtime vector ID must be portable")
        if not re.fullmatch(r"ecuc:/[^\s/*~]+(?:/[^\s/*~]+)*", row["object_id"]):
            raise ValueError("Runtime object identity must be exact")
        for key in ("com_ipdu", "route", "canif_pdu"):
            if not re.fullmatch(r"/[^\s/*~]+(?:/[^\s/*~]+)*", row[key]):
                raise ValueError("Runtime path identities must be exact")
        if (
            row["direction"] not in ("tx", "rx")
            or type(row["frame_id"]) is not int
            or not 0 <= row["frame_id"] <= 0x7FF
        ):
            raise ValueError("Runtime links support tx/rx standard classic CAN IDs")
        selected = row["policy_ids"]
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(x, str) or x not in known for x in selected)
            or len(set(selected)) != len(selected)
        ):
            raise ValueError("Runtime links require unique declared policy IDs")
        if not any(
            p["id"] in selected and p["object_id"] == row["object_id"] for p in policies
        ):
            raise ValueError("Runtime object must have an explicit selected protection")
        ids.add(row["id"])
    return ids


def plan(bundle: Path) -> dict:
    result = preflight_communication(*(bundle / "inputs" / FILES[k] for k in FILES))
    for item, name in zip(result["source_artifacts"], FILES.values()):
        item["path"] = "bundle/inputs/" + name
    return result


def capture(path: Path, project: dict) -> dict[str, bytes]:
    snapshots = {
        "inputs/" + FILES[k]: (path.parent / v).read_bytes()
        for k, v in project["runtime"]["inputs"].items()
    }
    with tempfile.TemporaryDirectory(prefix="workbench-runtime-preflight-") as tmp:
        root = Path(tmp)
        (root / "inputs").mkdir()
        for name, data in snapshots.items():
            (root / name).write_bytes(data)
        compiled = plan(root)
    declared = {v["id"] for v in compiled["vectors"]}
    selected = {b["vector_id"] for b in project["runtime"]["bindings"]}
    if declared != selected:
        raise ValueError(
            "Every runtime vector must be explicitly bound, with no unknown vectors"
        )
    return snapshots


def preflight(
    project: dict, after: dict, compiled: dict, static: dict
) -> dict[str, dict]:
    result = {}
    vectors = {v["id"]: v for v in compiled["vectors"]}
    for binding in project["runtime"]["bindings"]:
        status, reason = "passed", "explicit_identity_bound"
        vector = vectors[binding["vector_id"]]
        objects = [
            (i, o)
            for i, o in enumerate(after["objects"])
            if o["id"] == binding["object_id"]
        ]
        paths = [
            (i, p)
            for i, p in enumerate(after["communication"]["paths"])
            if all(p[k] == binding[k] for k in ("com_ipdu", "route", "canif_pdu"))
        ]
        ports = [
            (i, o)
            for i, o in enumerate(after["objects"])
            if o["path"] == binding["canif_pdu"]
        ]
        witness = [f"/objects/{i}" for i, _ in objects] + [
            f"/communication/paths/{i}" for i, _ in paths
        ]
        expected_id = (
            "CanIfTxPduCanId" if binding["direction"] == "tx" else "CanIfRxPduCanId"
        )
        addresses = [
            (i, j, f)
            for i, port in ports
            for j, f in enumerate(port["parameters"])
            if f["definition"] == port["definition"] + "/" + expected_id
        ]
        witness += [f"/objects/{i}/parameters/{j}" for i, j, _ in addresses]
        if static["status"] != "passed":
            status, reason = "blocked", "static_acceptance_rejected"
        elif len(objects) > 1 or len(paths) > 1 or len(ports) > 1 or len(addresses) > 1:
            status, reason = "blocked", "ambiguous_runtime_identity"
        elif not objects or not paths or not ports or not addresses:
            status, reason = "unassessed", "runtime_identity_or_address_missing"
        elif objects[0][1]["conditional"] or addresses[0][2]["conditional"]:
            status, reason = "unassessed", "conditional_runtime_identity"
        elif objects[0][1]["path"] not in [m["node"] for m in paths[0][1]["members"]]:
            status, reason = "unassessed", "signal_not_member_of_path"
        elif paths[0][1]["status"] != "resolved":
            status, reason = "unassessed", "runtime_path_incomplete"
        elif (
            vector["message"] != binding["message"]
            or binding["signal"] not in vector["expected_raw_signals"]
            or vector["direction"] != binding["direction"]
            or paths[0][1]["direction"] != binding["direction"]
            or vector["frame_id"] != binding["frame_id"]
            or vector["is_extended_id"]
        ):
            status, reason = "unassessed", "declared_runtime_identity_mismatch"
        else:
            value = addresses[0][2]["value"]
            try:
                actual_id = int(value, 16 if value.lower().startswith("0x") else 10)
            except ValueError:
                actual_id = -1
            if actual_id != binding["frame_id"]:
                status, reason = "unassessed", "ecuc_frame_id_mismatch"
        result[binding["id"]] = {
            "status": status,
            "reason": reason,
            "witness_pointers": witness,
        }
    # One execution plan is gated as a whole; an unbound vector cannot run indirectly.
    if any(row["status"] != "passed" for row in result.values()):
        group_status = next(
            s
            for s in ("failed", "blocked", "unassessed")
            if any(r["status"] == s for r in result.values())
        )
        for row in result.values():
            if row["status"] == "passed":
                row.update(status=group_status, reason="another_binding_rejected")
    return result


def context(bundle: Path, project: dict, nonce: str) -> dict:
    return {
        "run_id": nonce,
        "candidate_sha256": sha256_file(bundle / "ecuc/after/ecuc-review.json"),
        "policy_sha256": sha(canonical(project["policies"]).encode()),
        "runtime_declaration_sha256": sha(canonical(project["runtime"]).encode()),
        "input_sha256": {
            k: sha256_file(bundle / "inputs" / v) for k, v in FILES.items()
        },
    }


def execute(
    bundle: Path, project: dict, after: dict, static: dict, config: BusConfig
) -> None:
    compiled = plan(bundle)
    checks = preflight(project, after, compiled, static)
    if (
        config.fd
        or config.receive_own_messages
        or not isinstance(config.channel, str)
        or not config.channel.strip()
    ):
        raise ValueError("Linked runtime requires classic CAN without self reception")
    nonce = uuid.uuid4().hex
    binding_context = context(bundle, project, nonce)
    actual = BusConfig(
        config.interface,
        config.channel + "-" + nonce
        if config.interface == "virtual"
        else config.channel,
    )
    permitted = all(c["status"] == "passed" for c in checks.values())
    report_path = ""
    if permitted and actual.interface in {"virtual", "socketcan"}:
        raw = run_declared_communication(
            bundle / "inputs/runtime.dbc",
            bundle / "inputs/runtime-intent.json",
            bundle / "inputs/runtime-vectors.json",
            actual,
            bundle / "runtime",
            execution_context=binding_context,
        )
        # P20 paths become relative to the enclosing portable project base.
        for sources in (raw["source_artifacts"], raw["plan"]["source_artifacts"]):
            for item, name in zip(sources, FILES.values()):
                item["path"] = "bundle/inputs/" + name
        if (
            raw["plan"] != compiled
            or raw["source_artifacts"] != compiled["source_artifacts"]
        ):
            raise ValueError("Runtime inputs drifted after linked preflight")
        report_path = "runtime/declared-runtime-report.json"
        (bundle / report_path).write_text(
            json.dumps(raw, indent=2) + "\n", encoding="utf-8"
        )
    record = {
        "schema_version": VERSION,
        "producer": {
            "workbench": __version__,
            "python": platform.python_version(),
            "python_can": version("python-can"),
            "cantools": version("cantools"),
        },
        "context": binding_context,
        "requested_config": asdict(config),
        "bus_config": asdict(actual),
        "runtime_path": report_path,
        "runtime_sha256": sha256_file(bundle / report_path) if report_path else "",
        "preflight": checks,
        "boundary": BOUNDARY,
    }
    (bundle / "runtime-link.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def validate_runtime(raw: dict, compiled: dict, record: dict, bundle: Path) -> None:
    if set(raw) != {
        "artifact_type",
        "schema_version",
        "started_at",
        "duration_ms",
        "bus_config",
        "backend_probe",
        "isolation",
        "source_artifacts",
        "plan",
        "status",
        "reason",
        "vector_count",
        "passed_count",
        "vectors",
        "execution_context",
    }:
        raise ValueError("Runtime observation requires a closed record")
    if (
        not same(raw.get("execution_context"), record["context"])
        or not same(raw.get("bus_config"), record["bus_config"])
        or not same(raw.get("plan"), compiled)
        or not same(raw.get("source_artifacts"), compiled["source_artifacts"])
    ):
        raise ValueError(
            "Runtime context, input or plan binding differs; historical evidence cannot satisfy this run"
        )
    if raw.get("schema_version") != "declared-communication-runtime-0.2":
        raise ValueError("Linked runtime requires a context-bound observation")
    vectors = {v["id"]: v for v in compiled["vectors"]}
    if set(raw["vectors"]) != set(vectors):
        raise ValueError("Runtime vectors are missing or unexpected")
    database = _load_dbc(bundle / "inputs/runtime.dbc")
    for identity, expected in vectors.items():
        actual = raw["vectors"][identity]
        if set(actual) != {
            "id",
            "message",
            "direction",
            "sender",
            "receiver",
            "status",
            "reason",
            "observed",
            "error",
            "cleanup",
        }:
            raise ValueError("Runtime vector requires a closed observation")
        if actual["sender"] != (
            "local" if expected["direction"] == "tx" else "peer"
        ) or actual["receiver"] != (
            "peer" if expected["direction"] == "tx" else "local"
        ):
            raise ValueError("Runtime endpoints disagree with direction")
        for key in ("id", "message", "direction"):
            if not same(actual[key], expected[key]):
                raise ValueError("Runtime vector identity differs")
        if actual["status"] not in ("passed", "failed", "blocked") or not isinstance(
            actual["reason"], str
        ):
            raise ValueError("Invalid runtime vector status")
        observation = actual["observed"]
        if actual["status"] == "passed":
            if (
                not observation
                or actual["reason"]
                or actual["error"]
                or len(actual["cleanup"]) != 2
                or {c["endpoint"] for c in actual["cleanup"]} != {"local", "peer"}
                or any(c["status"] != "passed" or c["error"] for c in actual["cleanup"])
            ):
                raise ValueError("Passed runtime lacks observation or cleanup")
            for key in ("frame_id", "is_extended_id", "dlc", "payload_hex"):
                if not same(observation[key], expected[key]):
                    raise ValueError(
                        "Passed runtime observation differs from compiled vector"
                    )
            if any(
                observation[k] is not False
                for k in ("is_fd", "is_remote_frame", "is_error_frame")
            ):
                raise ValueError("Passed runtime has unsupported frame flags")
            definition = database.get_message_by_name(expected["message"])
            payload = bytes.fromhex(observation["payload_hex"])
            for key, scaling in (("raw_signals", False), ("signals", True)):
                if not same(
                    observation[key],
                    definition.decode(payload, scaling=scaling, decode_choices=False),
                ):
                    raise ValueError("Decoded runtime values differ from actual frame")
        elif not actual["reason"]:
            raise ValueError("Nonpassing runtime requires a reason")
    probe = raw["backend_probe"]
    if probe["status"] == "available" and (
        not same(probe.get("config"), record["bus_config"])
        or raw["isolation"]["channel"] != record["bus_config"]["channel"]
        or raw["isolation"]["endpoint_lifetime"] != "per_vector"
    ):
        raise ValueError("Backend observation does not bind execution conditions")
    expected_reason = (
        probe["reason"]
        if probe["status"] != "available"
        else "vector_failed"
        if any(v["status"] != "passed" for v in raw["vectors"].values())
        else ""
    )
    if raw["reason"] != expected_reason:
        raise ValueError("Runtime reason differs from observations")
    expected_status = (
        probe["status"]
        if probe["status"] != "available"
        else "passed"
        if all(v["status"] == "passed" for v in raw["vectors"].values())
        else "failed"
    )
    if (
        raw["status"] != expected_status
        or raw["vector_count"] != len(vectors)
        or raw["passed_count"]
        != sum(v["status"] == "passed" for v in raw["vectors"].values())
    ):
        raise ValueError("Runtime aggregate differs from observations")
    if probe["status"] != "available" and any(
        v["status"] != "blocked" or v["observed"] is not None
        for v in raw["vectors"].values()
    ):
        raise ValueError("Unavailable backend cannot have successful observations")


def replay(bundle: Path, project: dict, after: dict, static: dict) -> dict[str, dict]:
    record = json.loads((bundle / "runtime-link.json").read_text(encoding="utf-8"))
    if set(record) != {
        "schema_version",
        "producer",
        "context",
        "requested_config",
        "bus_config",
        "runtime_path",
        "runtime_sha256",
        "preflight",
        "boundary",
    }:
        raise ValueError("Runtime link requires a closed record")
    if (
        not isinstance(record["producer"], dict)
        or set(record["producer"]) != {"workbench", "python", "python_can", "cantools"}
        or any(not isinstance(v, str) or not v for v in record["producer"].values())
    ):
        raise ValueError("Runtime link requires recorded tool versions")
    compiled = plan(bundle)
    checks = preflight(project, after, compiled, static)
    nonce = record["context"]["run_id"]
    if (
        not isinstance(nonce, str)
        or not re.fullmatch(r"[0-9a-f]{32}", nonce)
        or record["context"] != context(bundle, project, nonce)
        or record["preflight"] != checks
        or record["boundary"] != BOUNDARY
        or record["schema_version"] != VERSION
    ):
        raise ValueError("Runtime link differs from frozen inputs and static checks")
    requested = BusConfig(**record["requested_config"])
    expected_config = asdict(
        BusConfig(
            requested.interface,
            requested.channel + "-" + nonce
            if requested.interface == "virtual"
            else requested.channel,
        )
    )
    if (
        not same(record["bus_config"], expected_config)
        or requested.fd
        or requested.receive_own_messages
    ):
        raise ValueError("Runtime execution conditions differ")
    permitted = all(
        c["status"] == "passed" for c in checks.values()
    ) and requested.interface in {"virtual", "socketcan"}
    raw = None
    if permitted:
        if (
            record["runtime_path"] != "runtime/declared-runtime-report.json"
            or sha256_file(bundle / record["runtime_path"]) != record["runtime_sha256"]
        ):
            raise ValueError("Expected runtime evidence is missing or changed")
        raw = json.loads((bundle / record["runtime_path"]).read_text(encoding="utf-8"))
        validate_runtime(raw, compiled, record, bundle)
    elif (
        record["runtime_path"]
        or record["runtime_sha256"]
        or (bundle / "runtime").exists()
    ):
        raise ValueError("Rejected static gate must not contain runtime execution")
    result = {}
    for binding in project["runtime"]["bindings"]:
        check = checks[binding["id"]]
        status, reason = check["status"], check["reason"]
        if status == "passed":
            if raw is None:
                status, reason = "blocked", "unsupported_backend"
            else:
                observation = raw["vectors"][binding["vector_id"]]
                status, reason = (
                    observation["status"],
                    observation["reason"] or "same_run_observed",
                )
        result["runtime." + binding["id"]] = {
            "status": status,
            "reason": reason,
            "evidence": {
                "path": "runtime-link.json",
                "pointer": "/preflight/" + binding["id"],
            },
            "affected_objects": [binding["object_id"]],
            "binding": binding,
            "run_id": nonce,
            "runtime_pointer": "/vectors/" + binding["vector_id"] if raw else "",
            "runtime_path": record["runtime_path"],
            "witness_pointers": check["witness_pointers"],
        }
    return result
