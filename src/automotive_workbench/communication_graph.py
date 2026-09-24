"""Source-bound, vendor-neutral communication intent graph and impact analysis.

Edges describe configuration dependencies, not calls in an AUTOSAR implementation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import quote

from automotive_workbench.adapters.dbc import _cantools
from automotive_workbench.communication_plan import validate_declaration

KINDS = {
    "com_signal": "ComSignal",
    "i_pdu": "IPdu",
    "pdur_route": "PduRRoute",
    "canif_pdu": "CanIfPdu",
}
PROPERTIES = (
    "start_bit",
    "bit_length",
    "byte_order",
    "is_signed",
    "scale",
    "offset",
    "minimum",
    "maximum",
    "unit",
)


def _json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON member: {key}")
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise ValueError(f"Non-finite JSON value: {value}")

    result = json.loads(
        raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=invalid
    )
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object")
    return result


def compile_graph(
    namespace: str, intent: dict[str, Any], dbc: dict[str, Any]
) -> dict[str, Any]:
    """Pure graph compilation; dbc uses inspect_dbc message/signal fields."""
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("A stable project namespace is required")
    if (
        intent.get("schema_version") != "bsw-intent-0.2"
        or not isinstance(intent.get("local_ecu"), str)
        or not intent["local_ecu"].strip()
    ):
        raise ValueError("Graph requires bsw-intent-0.2 with local_ecu")
    for key in ("messages", "signals"):
        if not isinstance(intent.get(key), list) or not all(
            isinstance(x, dict) for x in intent[key]
        ):
            raise ValueError(f"Intent requires {key} objects")
    for collection in ("messages", "signals"):
        for item in intent[collection]:
            for field in ("direction", "dbc_message", "dbc_signal", *KINDS):
                if field in item and not isinstance(item[field], str):
                    raise ValueError(f"Intent {field} must be a string")
            for field in ("can_id", "dlc", "start_bit", "bit_length"):
                if field in item and type(item[field]) is not int:
                    raise ValueError(f"Intent {field} must be an integer")
            for field in ("scale", "offset", "minimum", "maximum"):
                if (
                    field in item
                    and item[field] is not None
                    and type(item[field]) not in (int, float)
                ):
                    raise ValueError(f"Intent {field} must be numeric")
            if "is_signed" in item and type(item["is_signed"]) is not bool:
                raise ValueError("Intent is_signed must be boolean")
            for field in ("unit", "byte_order"):
                if field in item and not isinstance(item[field], str):
                    raise ValueError(f"Intent {field} must be a string")
            if not isinstance(item.get("unknowns", []), list):
                raise ValueError("Intent unknowns must be a list")
    nodes: dict[str, Any] = {}
    edges: dict[tuple[str, str, str], Any] = {}
    findings: list[dict[str, Any]] = []
    unknowns = {
        "Vendor ECUC, controller/hardware mapping, scheduling and runtime behavior are unverified"
    }
    scope = namespace + "/" + intent["local_ecu"]

    def identity(field: str, name: str) -> str:
        return "/".join(
            quote(x, safe="")
            for x in (namespace, intent["local_ecu"], KINDS[field], name)
        )

    def issue(code: str, locator: str, detail: str) -> None:
        findings.append(
            {"code": code, "source": "intent", "locator": locator, "detail": detail}
        )

    def node(
        field: str,
        item: dict[str, Any],
        locator: str,
        attributes: dict[str, Any],
        *,
        shared: bool = False,
    ) -> str | None:
        name = item.get(field)
        if not isinstance(name, str) or not name.strip():
            issue(
                "GRAPH-MISSING-REFERENCE",
                locator + "/" + field,
                "Missing object identity",
            )
            return None
        key = identity(field, name)
        source = {"artifact": "intent", "locator": locator + "/" + field}
        value = {
            "id": key,
            "kind": KINDS[field],
            "name": name,
            "direction": item.get("direction", "unknown"),
            "attributes": attributes,
            "sources": [source],
        }
        if value["direction"] not in {"tx", "rx"}:
            value["direction"] = "unknown"
            issue("GRAPH-DIRECTION", locator, "Direction must be tx or rx")
        if key in nodes:
            old = nodes[key]
            if not shared or any(
                old[k] != value[k] for k in ("direction", "attributes")
            ):
                issue("GRAPH-DUPLICATE-IDENTITY", locator + "/" + field, key)
            old["sources"].append(source)
        else:
            nodes[key] = value
        return key

    messages: dict[str, Any] = {}
    actual_messages = {x["name"]: x for x in dbc["messages"]}
    for index, item in enumerate(intent["messages"]):
        loc = f"/messages/{index}"
        name = item.get("dbc_message")
        if not isinstance(name, str) or not name:
            issue("GRAPH-MISSING-REFERENCE", loc, "Missing dbc_message")
            continue
        if name in messages:
            issue(
                "GRAPH-DUPLICATE-IDENTITY",
                loc,
                "Duplicate DBC message mapping: " + name,
            )
        messages[name] = item
        actual = actual_messages.get(name)
        if actual is None:
            issue("GRAPH-MISSING-REFERENCE", loc + "/dbc_message", name)
        else:
            if (
                item.get("dlc") != actual["dlc"]
                or item.get("can_id") != actual["frame_id"]
            ):
                issue(
                    "GRAPH-LENGTH-LAYOUT",
                    loc,
                    "DBC frame ID or DLC differs from intent",
                )
            wire_bits: set[int] = set()
            for wire_signal in actual["signals"]:
                bit = wire_signal["start_bit"]
                for _ in range(wire_signal["bit_length"]):
                    if bit < 0 or bit >= actual["dlc"] * 8 or bit in wire_bits:
                        issue(
                            "GRAPH-LENGTH-LAYOUT",
                            loc,
                            "DBC signal layout overlaps or exceeds PDU: "
                            + wire_signal["name"],
                        )
                        break
                    wire_bits.add(bit)
                    bit = (
                        bit + 1
                        if wire_signal["byte_order"] == "little_endian"
                        else (bit + 15 if bit % 8 == 0 else bit - 1)
                    )
            if actual.get("unsupported"):
                unknowns.add("Unsupported DBC semantics: " + name)
                issue(
                    "GRAPH-UNSUPPORTED",
                    loc,
                    "FD, multiplexing or float encoding is outside this graph subset",
                )
            if actual.get("direction") != item.get("direction"):
                issue(
                    "GRAPH-DIRECTION",
                    loc + "/direction",
                    "DBC local ECU direction differs from intent",
                )
        attrs = {
            "dbc_message": name,
            "can_id": item.get("can_id"),
            "dlc": item.get("dlc"),
            "dbc": actual,
        }
        node("i_pdu", item, loc, attrs)
        node("canif_pdu", item, loc, attrs)

    seen_signals: set[tuple[str, str]] = set()
    occupied: dict[str, dict[int, str]] = {}
    for index, item in enumerate(intent["signals"]):
        loc = f"/signals/{index}"
        name, signal = item.get("dbc_message"), item.get("dbc_signal")
        if not isinstance(name, str) or not isinstance(signal, str):
            issue("GRAPH-MISSING-REFERENCE", loc, "Missing DBC signal identity")
            continue
        if (name, signal) in seen_signals:
            issue("GRAPH-DUPLICATE-IDENTITY", loc, "Duplicate DBC signal mapping")
        seen_signals.add((name, signal))
        parent = messages.get(name)
        actual_message = actual_messages.get(name)
        actual = (
            next((s for s in actual_message["signals"] if s["name"] == signal), None)
            if actual_message
            else None
        )
        if parent is None or actual is None:
            issue(
                "GRAPH-MISSING-REFERENCE", loc, "Unresolved DBC message/signal mapping"
            )
        if parent and parent.get("direction") != item.get("direction"):
            issue(
                "GRAPH-DIRECTION",
                loc + "/direction",
                "Signal and message directions differ",
            )
        if actual and actual_message is not None:
            if any(p in item and item[p] != actual[p] for p in PROPERTIES):
                issue("GRAPH-LENGTH-LAYOUT", loc, "Signal properties differ from DBC")
            bits = []
            bit = actual["start_bit"]
            for _ in range(actual["bit_length"]):
                bits.append(bit)
                bit = (
                    bit + 1
                    if actual["byte_order"] == "little_endian"
                    else (bit + 15 if bit % 8 == 0 else bit - 1)
                )
            used = occupied.setdefault(name, {})
            if any(
                b < 0
                or b >= actual_message["dlc"] * 8
                or (b in used and used[b] != signal)
                for b in bits
            ):
                issue(
                    "GRAPH-LENGTH-LAYOUT",
                    loc,
                    "Signal outside PDU or overlapping another mapped signal",
                )
            used.update({b: signal for b in bits})
        attrs = {
            "dbc_message": name,
            "dbc_signal": signal,
            "dbc": actual,
            "declared": {p: item[p] for p in PROPERTIES if p in item},
        }
        ids: dict[str, str | None] = {
            "com_signal": node("com_signal", item, loc, attrs)
        }
        for field in ("i_pdu", "canif_pdu"):
            ref = item.get(field)
            ref_key = identity(field, ref) if isinstance(ref, str) and ref else None
            ids[field] = ref_key
            if ref_key not in nodes:
                issue(
                    "GRAPH-MISSING-REFERENCE", loc + "/" + field, "Unresolved " + field
                )
            elif parent and ref != parent.get(field):
                issue(
                    "GRAPH-ROUTE-ENDPOINT",
                    loc + "/" + field,
                    "Endpoint belongs to a different message",
                )
        ids["pdur_route"] = node(
            "pdur_route",
            item,
            loc,
            {
                "dbc_message": name,
                "i_pdu": item.get("i_pdu"),
                "canif_pdu": item.get("canif_pdu"),
            },
            shared=True,
        )
        for left, right, kind in (
            ("com_signal", "i_pdu", "signal-in-pdu"),
            ("i_pdu", "pdur_route", "pdu-route"),
            ("pdur_route", "canif_pdu", "route-canif"),
        ):
            source, target = ids[left], ids[right]
            if source in nodes and target in nodes:
                edge_key = (source, target, kind)
                edge = edges.setdefault(
                    edge_key,
                    {"source": source, "target": target, "kind": kind, "sources": []},
                )
                edge["sources"].append({"artifact": "intent", "locator": loc})
        for value in item.get("unknowns", []):
            unknowns.add(str(value))
    if not nodes or not intent["signals"]:
        issue("GRAPH-MISSING-REFERENCE", "/", "Empty communication model")
    return {
        "schema_version": "communication-graph-0.1",
        "scope": scope,
        "namespace": namespace,
        "local_ecu": intent["local_ecu"],
        "status": "failed" if findings else "passed",
        "nodes": sorted(nodes.values(), key=lambda x: x["id"]),
        "edges": sorted(
            edges.values(), key=lambda x: (x["source"], x["target"], x["kind"])
        ),
        "findings": findings,
        "unknowns": sorted(unknowns),
    }


def build_project_graph(
    project_path: Path, snapshots: dict[str, bytes] | None = None
) -> dict[str, Any]:
    """Read input snapshots once; parse and hash the same bytes, without opening CAN."""
    raw = snapshots["project"] if snapshots is not None else project_path.read_bytes()
    project = _json(raw)
    if project.get("schema_version") != "workbench-project-0.3":
        raise ValueError("Graph entry requires workbench-project-0.3")
    namespace = project.get("comparison_key")
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("Project comparison_key is required")
    inputs = project.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {
        "dbc",
        "intent",
        "contract",
        "vectors",
    }:
        raise ValueError("Project requires dbc, intent, contract and vectors")
    if snapshots is None:
        snapshots = {"project": raw}
        for key, value in inputs.items():
            if not isinstance(value, str) or not value:
                raise ValueError("Input path must be a string")
            snapshots[key] = (project_path.parent / value).read_bytes()
    if set(snapshots) != {"project", "dbc", "intent", "contract", "vectors"}:
        raise ValueError("Invalid graph source inventory")
    intent = _json(snapshots["intent"])
    cantools = _cantools()
    try:
        database = cantools.database.load_string(
            snapshots["dbc"].decode("utf-8-sig"), database_format="dbc", strict=False
        )
    except cantools.database.errors.Error as exc:
        raise ValueError(f"Invalid DBC input: {exc}") from exc
    dbc: dict[str, Any] = {"messages": []}
    for message in database.messages:
        receivers = {r for s in message.signals for r in s.receivers}
        direction = (
            "tx"
            if intent.get("local_ecu") in message.senders
            else "rx"
            if intent.get("local_ecu") in receivers
            else "unknown"
        )
        dbc["messages"].append(
            {
                "name": message.name,
                "frame_id": message.frame_id,
                "dlc": message.length,
                "extended": message.is_extended_frame,
                "direction": direction,
                "unsupported": message.is_fd
                or message.is_multiplexed()
                or any(s.is_float for s in message.signals),
                "signals": [
                    {
                        "name": s.name,
                        "start_bit": s.start,
                        "bit_length": s.length,
                        "byte_order": s.byte_order,
                        "is_signed": s.is_signed,
                        "scale": s.scale,
                        "offset": s.offset,
                        "minimum": s.minimum,
                        "maximum": s.maximum,
                        "unit": s.unit or "",
                    }
                    for s in message.signals
                ],
            }
        )
    graph = compile_graph(namespace, intent, dbc)
    graph["source_artifacts"] = [
        {
            "id": key,
            "sha256": hashlib.sha256(value).hexdigest(),
            "content_base64": base64.b64encode(value).decode("ascii"),
        }
        for key, value in sorted(snapshots.items())
    ]
    graph["vectors"] = validate_declaration(_json(snapshots["vectors"]))["vectors"]
    requirements = project.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Project requires acceptance items")
    seen = set()
    for req in requirements:
        if not isinstance(req, dict) or set(req) != {
            "id",
            "text",
            "stage",
            "pointer",
            "expected",
        }:
            raise ValueError("Invalid acceptance item")
        if any(
            not isinstance(req[k], str) or not req[k]
            for k in ("id", "text", "stage", "pointer")
        ):
            raise ValueError("Acceptance item fields must be nonempty strings")
        if (
            req["id"] in seen
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", req["id"])
            or re.search(r"~(?![01])", req["pointer"])
            or not req["pointer"].startswith("/")
            or req["stage"]
            not in {"canonical", "mapping", "communication", "generation"}
        ):
            raise ValueError("Invalid acceptance identity, stage or pointer")
        if type(req["expected"]) not in (str, int, float, bool, type(None)):
            raise ValueError("Acceptance expected value must be scalar")
        seen.add(req["id"])
    graph["requirements"] = requirements
    for vector in graph["vectors"]:
        mapped = [
            s for s in intent["signals"] if s.get("dbc_message") == vector["message"]
        ]
        if not mapped or any(
            s.get("direction") != vector["direction"]
            or s.get("dbc_signal") not in vector["signals"]
            for s in mapped
        ):
            graph["findings"].append(
                {
                    "code": "GRAPH-MISSING-REFERENCE",
                    "source": "vectors",
                    "locator": "/vectors/" + str(graph["vectors"].index(vector)),
                    "detail": "Vector does not cover its mapped communication path",
                }
            )
            graph["status"] = "failed"
    missing = {s.get("dbc_message") for s in intent["signals"]} - {
        v["message"] for v in graph["vectors"]
    }
    if missing:
        graph["unknowns"].append(
            "No runtime vector for mapped messages: " + ", ".join(sorted(missing))
        )
    graph["generation"] = project.get("generation")
    if graph["generation"] is not None:
        if not isinstance(graph["generation"], dict):
            raise ValueError("Project generation must be an object")
        graph["unknowns"].append(
            "Generation external artifacts are outside the graph; run the project generation gate"
        )
    for node in graph["nodes"]:
        message_name = node["attributes"].get("dbc_message")
        actual_message = next(
            (m for m in dbc["messages"] if m["name"] == message_name), None
        )
        if actual_message is None or (
            "dbc_signal" in node["attributes"]
            and not any(
                x["name"] == node["attributes"]["dbc_signal"]
                for x in actual_message["signals"]
            )
        ):
            continue
        node["sources"].append(
            {
                "artifact": "dbc",
                "locator": "message:"
                + quote(message_name, safe="")
                + (
                    "/signal:" + quote(node["attributes"]["dbc_signal"], safe="")
                    if "dbc_signal" in node["attributes"]
                    else ""
                ),
            }
        )
    return graph


def compare_graphs(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Conservative undirected dependency closure, retaining a witness per object."""
    result: dict[str, Any] = {
        "schema_version": "communication-impact-0.1",
        "status": "passed",
        "reason": "comparable",
        "baseline": before,
        "candidate": after,
        "source_changes": sorted(
            s["id"]
            for s in after["source_artifacts"]
            if next(
                (b["sha256"] for b in before["source_artifacts"] if b["id"] == s["id"]),
                None,
            )
            != s["sha256"]
        ),
        "locator_changes": [],
        "changes": [],
        "affected": [],
        "vectors": [],
        "requirements": [],
        "unknowns": sorted(set(before["unknowns"] + after["unknowns"])),
    }
    if (before["namespace"], before["local_ecu"]) != (
        after["namespace"],
        after["local_ecu"],
    ):
        result.update(
            status="not-comparable", reason="Project namespace or local ECU differs"
        )
        return result
    if before["status"] != "passed" or after["status"] != "passed":
        result.update(
            status="not-comparable",
            reason="Invalid graph; repair findings before impact analysis",
        )
        return result
    old = {n["id"]: n for n in before["nodes"]}
    new = {n["id"]: n for n in after["nodes"]}

    def semantic(n: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in n.items() if k != "sources"}

    result["locator_changes"] = sorted(
        key
        for key in old.keys() & new.keys()
        if old[key]["sources"] != new[key]["sources"]
    )
    seeds = []
    for key in sorted(old.keys() | new.keys()):
        kind = (
            "added"
            if key not in old
            else "removed"
            if key not in new
            else "modified"
            if semantic(old[key]) != semantic(new[key])
            else None
        )
        if kind:
            seeds.append(key)
            result["changes"].append({"id": key, "kind": kind})
    neighbors: dict[str, set[str]] = {}
    for graph in (before, after):
        for edge in graph["edges"]:
            neighbors.setdefault(edge["source"], set()).add(edge["target"])
            neighbors.setdefault(edge["target"], set()).add(edge["source"])
    paths = {key: [key] for key in seeds}
    queue = deque(seeds)
    while queue:
        key = queue.popleft()
        for neighbor in sorted(neighbors.get(key, set())):
            if neighbor not in paths:
                paths[neighbor] = paths[key] + [neighbor]
                queue.append(neighbor)
    result["affected"] = [{"id": key, "path": paths[key]} for key in sorted(paths)]
    messages = {
        (new.get(key) or old[key])["attributes"]["dbc_message"] for key in paths
    }
    vectors = {
        v["id"]
        for g in (before, after)
        for v in g["vectors"]
        if v["message"] in messages
    }
    # Definition drift is itself a rerun trigger, independent of graph changes.
    if (
        before["vectors"] != after["vectors"]
        or before["requirements"] != after["requirements"]
        or before["generation"] != after["generation"]
    ):
        vectors.update(v["id"] for g in (before, after) for v in g["vectors"])
        result["unknowns"].append(
            "Test definitions changed; all declared acceptance items need review"
        )
    old_hashes = {s["id"]: s["sha256"] for s in before["source_artifacts"]}
    other_changed = [
        s["id"]
        for s in after["source_artifacts"]
        if s["id"] == "contract" and old_hashes.get(s["id"]) != s["sha256"]
    ]
    if other_changed:
        result["unknowns"].append(
            "Canonical contract changed outside the communication graph; rerun all acceptance items"
        )
    uncovered = messages - {v["message"] for g in (before, after) for v in g["vectors"]}
    if uncovered:
        result["unknowns"].append(
            "Affected messages have no declared runtime vector: "
            + ", ".join(sorted(uncovered))
        )
    result["vectors"] = sorted(vectors)
    requirements = set()
    for graph in (before, after):
        for req in graph["requirements"]:
            pointer = req["pointer"]
            tokens = pointer.split("/")
            vector = (
                tokens[2].replace("~1", "/").replace("~0", "~")
                if len(tokens) > 2 and tokens[1] == "vectors"
                else None
            )
            if (
                other_changed
                or before["requirements"] != after["requirements"]
                or before["generation"] != after["generation"]
                or (messages and vector is None)
                or (vectors and (vector is None or vector in vectors))
            ):
                requirements.add(req["id"])
    result["requirements"] = sorted(requirements)
    return result


def run_graph(
    project: Path, output: Path, candidate: Path | None = None
) -> dict[str, Any]:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be absent or empty")
    if output.is_symlink():
        raise ValueError("Output must not be a symlink")
    graph = build_project_graph(project)
    result = (
        compare_graphs(graph, build_project_graph(candidate)) if candidate else graph
    )
    serialized = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        serialized,
        encoding="utf-8",
    )
    summary = [
        "# Communication configuration " + ("impact" if candidate else "graph"),
        "",
        "Status: " + result["status"],
        "",
        "Configuration dependencies only; this is not runtime or vendor ECUC validation.",
        "",
    ]
    if candidate:
        summary += [
            f"Changed objects: {len(result['changes'])}; affected objects: {len(result['affected'])}",
            "",
            "Rerun acceptance IDs: " + ", ".join(result["requirements"]),
            "",
            result["reason"],
        ]
    else:
        summary += [
            f"Objects: {len(graph['nodes'])}; relationships: {len(graph['edges'])}",
            "",
        ] + [
            f"- {f['code']} at {f['locator']}: {f['detail']}" for f in graph["findings"]
        ]
    if candidate:
        summary += ["", "Changed objects:", ""] + [
            f"- {x['kind']}: {x['id']}" for x in result["changes"]
        ]
        summary += ["", "Impact dependency paths:", ""] + [
            "- " + " → ".join(x["path"]) for x in result["affected"]
        ]
        summary += ["", "Changed source bytes: " + ", ".join(result["source_changes"])]
    summary += ["", "Unknowns:", ""] + ["- " + x for x in result["unknowns"]]
    (output / "report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return result


def verify_graph_report(path: Path) -> dict[str, Any]:
    """Replay embedded source snapshots; checks integrity, not producer identity."""
    try:
        report = _json(path.read_bytes())

        def rebuild(graph: dict[str, Any]) -> dict[str, Any]:
            snapshots = {}
            for source in graph["source_artifacts"]:
                raw = base64.b64decode(source["content_base64"], validate=True)
                if (
                    source["id"] in snapshots
                    or hashlib.sha256(raw).hexdigest() != source["sha256"]
                ):
                    raise ValueError("Duplicate source or source hash mismatch")
                snapshots[source["id"]] = raw
            return build_project_graph(Path("embedded-project.json"), snapshots)

        if report.get("schema_version") == "communication-graph-0.1":
            expected = rebuild(report)
        elif report.get("schema_version") == "communication-impact-0.1":
            expected = compare_graphs(
                rebuild(report["baseline"]), rebuild(report["candidate"])
            )
        else:
            raise ValueError("Unsupported graph report version")
        if report != expected:
            raise ValueError("Report differs from source replay")
        return {"status": "passed", "reason": "Embedded input replay matches report"}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {"status": "failed", "reason": str(exc)}
