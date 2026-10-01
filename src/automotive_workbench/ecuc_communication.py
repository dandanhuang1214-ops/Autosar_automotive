"""Bounded ECUC reference chains; structural evidence, never vendor validation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from automotive_workbench.ecuc_project import read_project, safe_file, sha

VERSION = "ecuc-communication-0.1"
# Owner type -> reference definition short name -> expected target type.
RULES = {
    "ComIPdu": {
        "ComIPduSignalRef": "ComSignal",
        "ComIPduSignalGroupRef": "ComSignalGroup",
        "ComPduIdRef": "Pdu",
    },
    "PduRSrcPdu": {"PduRSrcPduRef": "Pdu"},
    "PduRDestPdu": {"PduRDestPduRef": "Pdu"},
    "CanIfTxPduCfg": {"CanIfTxPduRef": "Pdu", "CanIfTxPduBufferRef": "CanIfBufferCfg"},
    "CanIfRxPduCfg": {"CanIfRxPduRef": "Pdu", "CanIfRxPduHrhIdRef": "CanIfHrhCfg"},
    "CanIfBufferCfg": {"CanIfBufferHthRef": "CanIfHthCfg"},
    "CanIfHthCfg": {"CanIfHthIdSymRef": "CanHardwareObject"},
    "CanIfHrhCfg": {"CanIfHrhIdSymRef": "CanHardwareObject"},
    "CanHardwareObject": {"CanControllerRef": "CanController"},
}
TYPES = {
    "Com": {"ComIPdu", "ComSignal", "ComSignalGroup", "ComGroupSignal"},
    "EcuC": {"Pdu"},
    "PduR": {"PduRRoutingPath", "PduRSrcPdu", "PduRDestPdu"},
    "CanIf": {
        "CanIfTxPduCfg",
        "CanIfRxPduCfg",
        "CanIfBufferCfg",
        "CanIfHthCfg",
        "CanIfHrhCfg",
    },
    "Can": {"CanHardwareObject", "CanController"},
}
SCOPE = [
    "Structural Com/EcuC/PduR/CanIf/Can chains using explicit references and containment only.",
    "Definition short names are interpreted in their module context; full definitions and XML locations are retained.",
    "R24-11 field vocabulary; no assertion that a vendor export conforms to this AUTOSAR release.",
    "No variant selection, gateway/transport routing, vendor validation, generation or physical ECU evidence.",
    "Resolved paths establish references and direction only, not timing, payload layout or runtime behavior.",
]
MAX_PATHS = 20000


def build(project: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    inspection, sources, containers = read_project(project)
    return build_model(inspection, sources, containers), sources


def build_model(inspection: dict[str, Any], sources: dict[str, bytes],
                containers: list[dict[str, Any]]) -> dict[str, Any]:
    module_types = {
        m["path"]: m["definition"].rsplit("/", 1)[-1] for m in inspection["modules"]
    }
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in containers:
        index[c["path"]].append(c)
    supported = [
        c
        for c in containers
        if c["type"] in TYPES.get(module_types[c["module"]], set())
    ]
    supported_paths = {c["path"] for c in supported}
    duplicate_modules = {
        m
        for m in inspection["selected_modules"]
        if sum(x["path"] == m for x in inspection["modules"]) != 1
    }
    edges: list[dict[str, Any]] = []
    by_role: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unassessed = []
    nodes = [{k: v for k, v in c.items() if k != "references"} for c in supported]

    def unique(path: str) -> dict[str, Any] | None:
        matches = index[path]
        if len(matches) != 1 or matches[0]["module"] in duplicate_modules:
            return None
        return matches[0]

    def add_edge(
        owner: dict[str, Any],
        target: str,
        role: str,
        definition: str,
        source: dict[str, str],
        expected: str,
        kind: str,
        conditional: bool = False,
    ) -> None:
        match = unique(target)
        if kind == "unassessed":
            resolution = "unassessed"
        elif (
            not unique(owner["path"])
            or len(index[target]) > 1
            or (index[target] and not match)
        ):
            resolution = "ambiguous"
        elif conditional or owner["conditional"] or (match and match["conditional"]):
            resolution = "conditional"
        elif not target:
            resolution = "empty"
        elif match and (match["type"] != expected or target not in supported_paths):
            resolution = "wrong-type"
        elif match:
            resolution = "resolved"
        elif any(
            target == m or target.startswith(m + "/")
            for m in inspection["selected_modules"]
        ):
            resolution = "missing"
        else:
            resolution = "unassessed"
        edge = {
            "id": f"edge-{len(edges):06d}",
            "owner": owner["path"],
            "target": target,
            "role": role,
            "definition": definition,
            "source": source,
            "expected_type": expected,
            "kind": kind,
            "resolution": resolution,
        }
        edges.append(edge)
        by_role[(owner["path"], role)].append(edge)

    for c in supported:
        for ref in c["references"]:
            role = ref["definition"].rsplit("/", 1)[-1]
            expected = RULES.get(c["type"], {}).get(role)
            if expected:
                add_edge(
                    c,
                    ref["target"],
                    role,
                    ref["definition"],
                    ref["source"],
                    expected,
                    "reference"
                    if ref["kind"] == "ECUC-REFERENCE-VALUE"
                    else "unassessed",
                    ref["conditional"],
                )
            else:
                unassessed.append(
                    {
                        "owner": c["path"],
                        **ref,
                        "reason": "Reference outside supported chain vocabulary",
                    }
                )
        parent = unique(c["parent"])
        if parent and (
            (
                parent["type"] == "PduRRoutingPath"
                and c["type"] in {"PduRSrcPdu", "PduRDestPdu"}
            )
            or (parent["type"] == "ComSignalGroup" and c["type"] == "ComGroupSignal")
        ):
            add_edge(
                parent, c["path"], "contains", "", c["source"], c["type"], "containment"
            )
    # Unknown vendor container types stay visible, even when their names resemble a chain node.
    unsupported_containers = [
        {"path": c["path"], "definition": c["definition"], "source": c["source"]}
        for c in containers
        if module_types[c["module"]] in TYPES and c["path"] not in supported_paths
    ]

    def parameter(c: dict[str, Any], key: str) -> str:
        values = [
            p for p in c["parameters"] if p["definition"].rsplit("/", 1)[-1] == key
        ]
        return (
            values[0]["value"]
            if len(values) == 1 and not values[0]["conditional"]
            else ""
        )

    def one(
        c: dict[str, Any], role: str, path: dict[str, Any]
    ) -> dict[str, Any] | None:
        refs = by_role[(c["path"], role)]
        path["edge_ids"].extend(e["id"] for e in refs)
        if len(refs) != 1:
            path["gaps"].append(
                f"{c['path']}: {role} requires one reference, found {len(refs)}"
            )
            return None
        edge = refs[0]
        if edge["resolution"] != "resolved":
            path["gaps"].append(f"{c['path']}: {role} is {edge['resolution']}")
            return None
        path["nodes"].append(edge["target"])
        return unique(edge["target"])

    def containment(
        parent: dict[str, Any], child: dict[str, Any], path: dict[str, Any]
    ) -> None:
        refs = [
            e
            for e in by_role[(parent["path"], "contains")]
            if e["target"] == child["path"]
        ]
        path["edge_ids"].extend(e["id"] for e in refs)
        if len(refs) != 1 or refs[0]["resolution"] != "resolved":
            path["gaps"].append(f"{child['path']}: unresolved containment")
        path["nodes"].append(child["path"])

    # Index exact global PDU targets; no comparisons of short names or Tx/Rx suffixes.
    endpoint_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in supported:
        role = {
            "PduRSrcPdu": "PduRSrcPduRef",
            "PduRDestPdu": "PduRDestPduRef",
            "CanIfTxPduCfg": "CanIfTxPduRef",
            "CanIfRxPduCfg": "CanIfRxPduRef",
        }.get(c["type"])
        if role:
            for e in by_role[(c["path"], role)]:
                endpoint_index[(c["type"], e["target"])].append(c)
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in supported:
        children[c["parent"]].append(c)
    paths: list[dict[str, Any]] = []

    def finish(path: dict[str, Any]) -> None:
        path["nodes"] = list(dict.fromkeys(path["nodes"]))
        path["edge_ids"] = list(dict.fromkeys(path["edge_ids"]))
        path["gaps"] = list(dict.fromkeys(path["gaps"]))
        path["status"] = "partial" if path["gaps"] else "resolved"
        paths.append(path)
        if len(paths) > MAX_PATHS:
            raise ValueError("ECUC communication exceeds the 20000 path limit")

    def clone(path: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(path))

    for com in [c for c in supported if c["type"] == "ComIPdu"]:
        direction = {"SEND": "tx", "RECEIVE": "rx"}.get(
            parameter(com, "ComIPduDirection"), "unknown"
        )
        base: dict[str, Any] = {
            "com_ipdu": com["path"],
            "direction": direction,
            "members": [],
            "route": "",
            "canif_pdu": "",
            "nodes": [com["path"]],
            "edge_ids": [],
            "gaps": [],
        }
        for role in ("ComIPduSignalRef", "ComIPduSignalGroupRef"):
            for edge in by_role[(com["path"], role)]:
                base["edge_ids"].append(edge["id"])
                if edge["resolution"] != "resolved":
                    base["gaps"].append(
                        f"{role}: {edge['resolution']} {edge['target']}"
                    )
                    continue
                base["members"].append({"node": edge["target"], "group": ""})
                if role == "ComIPduSignalGroupRef":
                    for e in by_role[(edge["target"], "contains")]:
                        base["edge_ids"].append(e["id"])
                        if e["resolution"] == "resolved":
                            base["members"].append(
                                {"node": e["target"], "group": edge["target"]}
                            )
                        else:
                            base["gaps"].append(
                                f"Group member {e['target']}: {e['resolution']}"
                            )
        if direction == "unknown":
            base["gaps"].append(
                "ComIPduDirection missing, duplicated, conditional or unsupported"
            )
        pdu = one(com, "ComPduIdRef", base)
        if pdu is None or direction == "unknown":
            finish(base)
            continue
        near_type, far_type = (
            ("PduRSrcPdu", "PduRDestPdu")
            if direction == "tx"
            else ("PduRDestPdu", "PduRSrcPdu")
        )
        endpoints = endpoint_index[(near_type, pdu["path"])]
        if not endpoints:
            base["gaps"].append(
                "No PduR endpoint in the configured communication direction"
            )
            finish(base)
        for near in endpoints:
            path = clone(base)
            one(near, near_type + "Ref", path)
            route = unique(near["parent"])
            if route is None or route["type"] != "PduRRoutingPath":
                path["gaps"].append("Routing path parent missing or ambiguous")
                finish(path)
                continue
            path["route"] = route["path"]
            path["nodes"].append(route["path"])
            containment(route, near, path)
            src_count = sum(c["type"] == "PduRSrcPdu" for c in children[route["path"]])
            if src_count != 1:
                path["gaps"].append(
                    f"Routing path requires one source, found {src_count}"
                )
            far_ends = [c for c in children[route["path"]] if c["type"] == far_type]
            if not far_ends:
                path["gaps"].append("Opposite PduR endpoint absent")
                finish(path)
            for far in far_ends:
                branch = clone(path)
                containment(route, far, branch)
                other_pdu = one(far, far_type + "Ref", branch)
                if other_pdu is None:
                    finish(branch)
                    continue
                canif_type = "CanIfTxPduCfg" if direction == "tx" else "CanIfRxPduCfg"
                matches = endpoint_index[(canif_type, other_pdu["path"])]
                if not matches:
                    branch["gaps"].append(
                        "No CanIf PDU in the configured communication direction"
                    )
                    finish(branch)
                for canif in matches:
                    chain = clone(branch)
                    if len(matches) != 1:
                        chain["gaps"].append(
                            "Global PDU maps to multiple CanIf configurations; selection is unassessed"
                        )
                    chain["canif_pdu"] = canif["path"]
                    chain["nodes"].append(canif["path"])
                    one(
                        canif,
                        "CanIfTxPduRef" if direction == "tx" else "CanIfRxPduRef",
                        chain,
                    )
                    current = canif
                    steps = (
                        ["CanIfTxPduBufferRef", "CanIfBufferHthRef", "CanIfHthIdSymRef"]
                        if direction == "tx"
                        else ["CanIfRxPduHrhIdRef", "CanIfHrhIdSymRef"]
                    )
                    for role in steps:
                        target = one(current, role, chain)
                        if target is None:
                            break
                        current = target
                    else:
                        if parameter(current, "CanObjectType") != (
                            "TRANSMIT" if direction == "tx" else "RECEIVE"
                        ):
                            chain["gaps"].append(
                                "CanObjectType conflicts with direction or is unassessed"
                            )
                        one(current, "CanControllerRef", chain)
                    finish(chain)
    report = {
        "schema_version": VERSION,
        "project": inspection["project"],
        "scope": SCOPE,
        "sources": inspection["sources"],
        "selected_modules": inspection["selected_modules"],
        "inspection_status": inspection["status"],
        "inspection_findings": inspection["findings"],
        "nodes": nodes,
        "edges": edges,
        "paths": paths,
        "unassessed_references": unassessed,
        "unsupported_containers": unsupported_containers,
        "status": "no-paths"
        if not paths
        else "partial"
        if any(p["status"] == "partial" for p in paths)
        else "resolved-in-scope",
    }
    return report


def run_communication(project: Path, output: Path) -> dict[str, Any]:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Communication output must be empty or absent")
    if output.resolve().is_relative_to(project.resolve().parent):
        raise ValueError("Communication output must be outside the source project")
    report, sources = build(project)
    for name, data in sources.items():
        target = output / "snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "ecuc-communication.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def verify_communication(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != VERSION
        or not isinstance(report.get("project"), str)
    ):
        raise ValueError("Unsupported ECUC communication report")
    snapshot = path.parent / "snapshot"
    if snapshot.is_symlink():
        raise ValueError("Snapshot root must not be a symlink")
    expected, sources = build(safe_file(snapshot, report["project"]))
    actual = {
        p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()
    }
    if any(p.is_symlink() for p in snapshot.rglob("*")) or actual != set(sources):
        raise ValueError("Snapshot inventory differs")
    if json.dumps(report, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("Saved communication report differs from replayed sources")
    return {
        "status": "passed",
        "schema_version": VERSION,
        "source_count": len(sources),
        "report_sha256": sha(path.read_bytes()),
        "communication_status": expected["status"],
    }
