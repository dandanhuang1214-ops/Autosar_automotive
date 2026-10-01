"""Replay-verified snapshot comparison with explicit dependency witnesses."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from automotive_workbench.ecuc_communication import TYPES, RULES as COMMUNICATION_RULES
from automotive_workbench.ecuc_integration import SW_TYPES, EVENTS, BSW_EVENTS, RULES
from automotive_workbench.ecuc_model import canonical, semantic
from automotive_workbench.ecuc_project import sha
from automotive_workbench.ecuc_review import check_output, read_verified, render

VERSION = "ecuc-configuration-impact-0.1"
KNOWN_TYPES = set().union(
    *TYPES.values(),
    SW_TYPES,
    EVENTS,
    BSW_EVENTS,
    {
        "SW-COMPONENT-PROTOTYPE",
        "COMPOSITION-SW-COMPONENT-TYPE",
        "SWC-INTERNAL-BEHAVIOR",
        "RUNNABLE-ENTITY",
        "BSW-SCHEDULABLE-ENTITY",
        "BSW-INTERNAL-BEHAVIOR",
        "AR-PACKAGE",
        "ECUC-MODULE-CONFIGURATION-VALUES",
        "OsTask",
        "OsEvent",
        "OsAlarm",
        "OsApplication",
        "OsScheduleTable",
        "OsScheduleTableExpiryPoint",
        "RteBswModuleInstance",
    },
    {k[1] for k in RULES},
    *(v[1] for v in RULES.values()),
)
SCOPE = [
    "Comparison of supplied snapshots by exact absolute object identity; no claim of cross-ECU semantic equivalence.",
    "Impact means explicit structural dependency or membership in a recorded communication/binding/mode path, not runtime causation.",
    "Opaque/vendor changes and scope changes remain unassessed; absence of an observed link is not proof of no impact.",
    "Historical tool observations are compared separately and never treated as current configuration failures.",
]
MAX_AFFECTED = 100000
PARAMETERS = {
    "ComSignal": {
        "ComBitSize",
        "ComBitPosition",
        "ComSignalType",
        "ComSignalEndianness",
        "ComSignalInitValue",
        "ComTransferProperty",
    },
    "ComGroupSignal": {
        "ComBitSize",
        "ComBitPosition",
        "ComSignalType",
        "ComSignalEndianness",
        "ComSignalInitValue",
        "ComTransferProperty",
    },
    "ComIPdu": {"ComIPduDirection", "ComIPduSignalProcessing", "ComIPduType"},
    "Pdu": {"PduLength"},
    "CanHardwareObject": {"CanObjectType", "CanObjectId", "CanHandleType", "CanIdType"},
    "CanController": {"CanControllerId", "CanControllerActivation"},
    "CanIfTxPduCfg": {
        "CanIfTxPduCanId",
        "CanIfTxPduId",
        "CanIfTxPduDlc",
        "CanIfTxPduDataLength",
    },
    "CanIfRxPduCfg": {
        "CanIfRxPduCanId",
        "CanIfRxPduId",
        "CanIfRxPduDlc",
        "CanIfRxPduDataLength",
    },
    "CanIfBufferCfg": {"CanIfBufferSize"},
    "OsTask": {"OsTaskPriority", "OsTaskActivation", "OsTaskSchedule"},
    "RteEventToTaskMapping": {
        "RtePositionInTask",
        "RteImmediateRestart",
        "RteActivationOffset",
        "RteOsSchedulePoint",
    },
    "RteBswEventToTaskMapping": {"RteBswPositionInTask", "RteBswImmediateRestart"},
    "BswMModeCondition": {"BswMConditionType"},
    "BswMLogicalExpression": {"BswMLogicalOperator"},
    "BswMRule": {"BswMRuleInitState"},
    "BswMActionListItem": {"BswMActionListItemIndex"},
    "TIMING-EVENT": {"PERIOD"},
    "BSW-TIMING-EVENT": {"PERIOD"},
}


def unknown_fields(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    """Opaque vendor fields retain uncertainty even inside otherwise supported types."""
    obj = right or left
    assert obj is not None
    for group in ("parameters", "references"):
        a = {canonical(x): x for x in (left or {}).get(group, [])}
        b = {canonical(x): x for x in (right or {}).get(group, [])}
        roles = {
            ((a.get(k) or b[k])["definition"]).rsplit("/", 1)[-1]
            for k in a.keys() ^ b.keys()
        }
        allowed = (
            PARAMETERS.get(obj["type"], set())
            if group == "parameters"
            else (
                set(COMMUNICATION_RULES.get(obj["type"], {}))
                | {k[2] for k in RULES if k[1] == obj["type"]}
                | ({"TYPE-TREF"} if obj["type"] == "SW-COMPONENT-PROTOTYPE" else set())
                | ({"START-ON-EVENT-REF"} if obj["type"] in EVENTS else set())
                | ({"STARTS-ON-EVENT-REF"} if obj["type"] in BSW_EVENTS else set())
            )
        )
        if roles - allowed:
            return True
    return False


def compute(
    before: dict[str, Any], after: dict[str, Any], before_sha: str, after_sha: str
) -> dict[str, Any]:
    duplicates = []
    indexes = []
    for side, review in [("before", before), ("after", after)]:
        index = {}
        for obj in review["objects"]:
            if obj["id"] in index:
                duplicates.append(side + ": " + obj["id"])
            index[obj["id"]] = obj
        indexes.append(index)
    old, new = indexes
    reasons = ["Ambiguous object identity: " + d for d in duplicates]
    if not set(before["selected_modules"]) & set(after["selected_modules"]):
        reasons.append("No common selected ECUC module identity")
    changes = []
    unknown = []
    if before["selected_modules"] != after["selected_modules"]:
        unknown.append(
            {
                "kind": "module-selection",
                "identity": "",
                "message": "Selection changed; removed/unread scope cannot establish absence.",
            }
        )
    for name in sorted(set(before["residuals"]) | set(after["residuals"])):
        if before["residuals"].get(name) != after["residuals"].get(name):
            unknown.append(
                {
                    "kind": "source-residual",
                    "identity": name,
                    "message": "Unmodeled source structure or input scope changed.",
                }
            )
    if not reasons:
        for identity in sorted(set(old) | set(new)):
            left, right = old.get(identity), new.get(identity)
            a, b = semantic(left) if left else None, semantic(right) if right else None
            if canonical(a) == canonical(b):
                continue
            fields = sorted(
                k
                for k in (set(a or {}) | set(b or {}))
                if canonical((a or {}).get(k)) != canonical((b or {}).get(k))
            )
            obj = right or left
            assert obj is not None
            changes.append(
                {
                    "object_id": identity,
                    "kind": "added"
                    if left is None
                    else "removed"
                    if right is None
                    else "modified",
                    "fields": fields,
                    "before": a,
                    "after": b,
                    "before_source": left["source"] if left else None,
                    "after_source": right["source"] if right else None,
                }
            )
            if (
                obj["type"] not in KNOWN_TYPES
                or unknown_fields(a, b)
                or (left and right and "opaque_sha256" in fields)
                or (
                    left
                    and right
                    and any(
                        k in fields for k in ("definition", "module", "conditional")
                    )
                )
            ):
                unknown.append(
                    {
                        "kind": "object-semantics",
                        "identity": identity,
                        "message": "Unknown type or opaque XML changed; semantic effect unassessed.",
                    }
                )
    affected = []
    path_impacts = []
    binding_impacts = []
    mode_impacts = []
    seeds = {c["object_id"] for c in changes}
    for side, review, index in [("before", before, old), ("after", after, new)]:
        reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
        edge_map = {e["id"]: e for e in review["integration"]["dependencies"]}
        for edge in edge_map.values():
            if edge["resolution"] == "resolved" and edge["dependency"]:
                reverse[edge["dependency"]].append(edge)
        # One deterministic shortest witness per affected object in each snapshot.
        witnesses: dict[str, dict[str, Any]] = {
            seed: {"origin": seed, "edges": []}
            for seed in sorted(seeds)
            if seed in index
        }
        queue = deque(witnesses)
        while queue:
            current = queue.popleft()
            for edge in reverse[current]:
                consumer = edge["consumer"]
                if consumer in witnesses:
                    continue
                witnesses[consumer] = {
                    "origin": witnesses[current]["origin"],
                    "edges": witnesses[current]["edges"] + [edge["id"]],
                }
                queue.append(consumer)
                if len(witnesses) > MAX_AFFECTED:
                    raise ValueError("Impact traversal exceeds supported object limit")
        for identity, witness in sorted(witnesses.items()):
            affected.append(
                {
                    "snapshot": side,
                    "object_id": identity,
                    "origin": witness["origin"],
                    "dependency_edges": witness["edges"],
                    "source": index[identity]["source"],
                }
            )
        for position, path in enumerate(review["communication"]["paths"]):
            members = {"ecuc:" + n for n in path["nodes"]} | {
                "ecuc:" + x["node"] for x in path["members"]
            }
            hits = sorted(members & witnesses.keys())
            if hits:
                path_impacts.append(
                    {
                        "snapshot": side,
                        "path_index": position,
                        "com_ipdu": path["com_ipdu"],
                        "direction": path["direction"],
                        "route": path["route"],
                        "canif_pdu": path["canif_pdu"],
                        "affected_members": hits,
                    }
                )
        for row in review["integration"]["bindings"]:
            members = {row["mapping"], *row["events"], *row["tasks"], *row["entities"]}
            hits = sorted(members & witnesses.keys())
            if hits:
                binding_impacts.append(
                    {
                        "snapshot": side,
                        "mapping": row["mapping"],
                        "affected_members": hits,
                    }
                )
        for row in review["integration"]["mode_rules"]:
            hits = sorted(set(row["objects"]) & witnesses.keys())
            if hits:
                mode_impacts.append(
                    {"snapshot": side, "rule": row["rule"], "affected_members": hits}
                )
    incomplete = {
        side: sum(
            e["resolution"] != "resolved" for e in review["integration"]["dependencies"]
        )
        for side, review in [("before", before), ("after", after)]
    }
    status = (
        "not-comparable"
        if reasons
        else "partial"
        if unknown
        else "changed-in-scope"
        if changes
        else "unchanged-in-scope"
    )
    return {
        "schema_version": VERSION,
        "status": status,
        "scope": SCOPE,
        "reviews": {
            "before": {"path": "before/ecuc-review.json", "sha256": before_sha},
            "after": {"path": "after/ecuc-review.json", "sha256": after_sha},
        },
        "reasons": reasons,
        "changes": changes,
        "unassessed_changes": unknown,
        "affected_objects": affected,
        "communication_impacts": path_impacts,
        "binding_impacts": binding_impacts,
        "mode_impacts": mode_impacts,
        "unresolved_dependency_counts": incomplete,
        "historical_logs_changed": canonical(before["historical_tool_logs"])
        != canonical(after["historical_tool_logs"]),
        "summary": {
            "changed_objects": len(changes),
            "affected_objects": len(affected),
            "communication_paths": len(path_impacts),
            "task_bindings": len(binding_impacts),
            "mode_rules": len(mode_impacts),
        },
    }


def compare_reviews(
    before_path: Path, after_path: Path, output: Path
) -> dict[str, Any]:
    check_output(output)
    for p in (before_path, after_path):
        if output.resolve().is_relative_to(
            p.parent.resolve()
        ) or p.parent.resolve().is_relative_to(output.resolve()):
            raise ValueError("Impact output must not overlap review inputs")
    before, after = read_verified(before_path), read_verified(after_path)
    result = compute(
        before, after, sha(before_path.read_bytes()), sha(after_path.read_bytes())
    )
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(before_path.parent, output / "before")
    shutil.copytree(after_path.parent, output / "after")
    (output / "ecuc-impact.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "index.html").write_text(
        render("ECUC configuration impact", result), encoding="utf-8"
    )
    return result


def verify_impact(path: Path) -> dict[str, Any]:
    if (
        path.name != "ecuc-impact.json"
        or path.is_symlink()
        or any(p.is_symlink() for p in path.parent.rglob("*"))
    ):
        raise ValueError("Invalid impact bundle path or symlink")
    saved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or saved.get("schema_version") != VERSION:
        raise ValueError("Unsupported impact report")
    if {p.name for p in path.parent.iterdir()} != {
        "before",
        "after",
        "ecuc-impact.json",
        "index.html",
    }:
        raise ValueError("Impact inventory differs")
    before_path, after_path = (
        path.parent / "before/ecuc-review.json",
        path.parent / "after/ecuc-review.json",
    )
    before, after = read_verified(before_path), read_verified(after_path)
    expected = compute(
        before, after, sha(before_path.read_bytes()), sha(after_path.read_bytes())
    )
    if canonical(saved) != canonical(expected) or (
        path.parent / "index.html"
    ).read_text(encoding="utf-8") != render("ECUC configuration impact", expected):
        raise ValueError("Impact differs from replayed review snapshots")
    return {
        "status": "passed",
        "schema_version": VERSION,
        "impact_status": expected["status"],
        "report_sha256": sha(path.read_bytes()),
    }
