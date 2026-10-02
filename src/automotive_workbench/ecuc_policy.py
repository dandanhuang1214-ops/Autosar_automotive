"""Exact object protections over replayable P26 facts, with bounded completeness."""

from __future__ import annotations

import re
from typing import Any

from automotive_workbench.ecuc_impact import unknown_fields


def validate_policies(value: Any) -> set[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("Object policies must be a nonempty array")
    ids: set[str] = set()
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Object policy must be an object")
        condition = row.get("condition")
        fields = {"id", "object_id", "condition"}
        if condition == "unchanged":
            fields |= {"field_group", "definition"}
        elif condition != "exists_complete":
            raise ValueError("Unsupported object policy condition")
        if set(row) != fields or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("Object policy fields differ from contract")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", row["id"]) or row["id"] in ids:
            raise ValueError("Object policy IDs must be unique portable identifiers")
        if not re.fullmatch(r"ecuc:/[^\s/*~]+(?:/[^\s/*~]+)*", row["object_id"]):
            raise ValueError("Object policy requires an exact absolute ECUC identity")
        if condition == "unchanged" and (
            row["field_group"] not in {"parameters", "references"}
            or not re.fullmatch(r"/[^\s/*~]+(?:/[^\s/*~]+)*", row["definition"])
        ):
            raise ValueError(
                "Immutable field requires an exact definition and supported group"
            )
        ids.add(row["id"])
    return ids


def observe(review: dict, policy: dict) -> dict[str, Any]:
    identity = policy["object_id"]
    matches = [(i, o) for i, o in enumerate(review["objects"]) if o["id"] == identity]
    result: dict[str, Any] = {
        "status": "passed",
        "reason": "observed",
        "object_pointers": [f"/objects/{i}" for i, _ in matches],
        "field_pointers": [],
        "values": [],
        "witness_pointers": [],
    }

    def stop(status: str, reason: str) -> dict[str, Any]:
        result.update(status=status, reason=reason)
        return result

    if len(matches) > 1:
        return stop("blocked", "ambiguous_object")
    if not matches:
        return stop("failed", "missing_object")
    index, obj = matches[0]
    if obj["conditional"]:
        return stop("unassessed", "conditional_object")
    if policy["condition"] == "unchanged":
        group = policy["field_group"]
        fields = [
            (i, f)
            for i, f in enumerate(obj[group])
            if f["definition"] == policy["definition"]
        ]
        result["field_pointers"] = [f"/objects/{index}/{group}/{i}" for i, _ in fields]
        result["values"] = [
            f["value" if group == "parameters" else "target"] for _, f in fields
        ]
        probe = {**obj, "parameters": [], "references": []}
        probe[group] = [f for _, f in fields] or [{"definition": policy["definition"]}]
        if unknown_fields(None, probe):
            return stop("unassessed", "unsupported_field")
        if len(fields) > 1:
            return stop("blocked", "ambiguous_field")
        if not fields:
            return stop("failed", "missing_field")
        if fields[0][1]["conditional"]:
            return stop("unassessed", "conditional_field")
        result["witness_pointers"] = [
            f"/integration/dependencies/{i}"
            for i, edge in enumerate(review["integration"]["dependencies"])
            if edge["consumer"] == identity and edge["source"] == fields[0][1]["source"]
        ]
        if group == "references":
            target = result["values"][0]
            targets = [o for o in review["objects"] if o["path"] == target]
            if len(targets) > 1:
                return stop("blocked", "ambiguous_target")
            if not targets:
                return stop("failed", "missing_target")
            if targets[0]["conditional"]:
                return stop("unassessed", "conditional_target")
        return result
    witnesses = []
    if obj["type"] in {"ComSignal", "ComGroupSignal", "ComIPdu"}:
        for i, row in enumerate(review["communication"]["paths"]):
            members = row["nodes"] + [m["node"] for m in row["members"]]
            if obj["path"] in members:
                witnesses.append((f"/communication/paths/{i}", row, "resolved"))
    elif obj["type"] in {
        "RteEventToTaskMapping",
        "RteBswEventToTaskMapping",
        "BswMRule",
    }:
        mode = obj["type"] == "BswMRule"
        section, key = ("mode_rules", "rule") if mode else ("bindings", "mapping")
        if not mode and not review["inputs"]["applications"]:
            return stop("unassessed", "application_coverage_missing")
        for i, row in enumerate(review["integration"][section]):
            if row[key] == identity:
                witnesses.append(
                    (f"/integration/{section}/{i}", row, "linked-in-scope")
                )
    else:
        return stop("unassessed", "unsupported_structure")
    result["witness_pointers"] = [p for p, _, _ in witnesses]
    if not witnesses:
        return stop("failed", "missing_structure")
    if any(r["status"] != expected or r["gaps"] for _, r, expected in witnesses):
        return stop("failed", "structural_gap")
    return result


def evaluate(policy: dict, before: dict, after: dict, impact: dict) -> dict[str, Any]:
    observations = {
        side: observe(review, policy)
        for side, review in (("before", before), ("after", after))
    }
    for side in observations:
        observations[side]["path"] = f"ecuc/{side}/ecuc-review.json"
    statuses = [o["status"] for o in observations.values()]
    status = next(
        (s for s in ("blocked", "failed", "unassessed") if s in statuses), "passed"
    )
    reason = next(
        (o["reason"] for o in observations.values() if o["status"] == status),
        "protected_structure_present",
    )
    if status == "passed" and policy["condition"] == "unchanged":
        changed = observations["before"]["values"] != observations["after"]["values"]
        status, reason = (
            ("failed", "protected_field_changed")
            if changed
            else ("passed", "protected_field_unchanged")
        )
    # Unknown source/scope changes cannot silently pass a mandatory protection.
    if status == "passed" and (
        impact["status"] in {"partial", "not-comparable"}
        or any(impact["unresolved_dependency_counts"].values())
    ):
        status = "blocked" if impact["status"] == "not-comparable" else "unassessed"
        reason = "impact_coverage_incomplete"
    affected = sorted(
        {
            x["object_id"]
            for x in impact["affected_objects"]
            if x["object_id"] == policy["object_id"]
        }
    )
    return {
        "status": status,
        "reason": reason,
        "evidence": {
            "path": "ecuc/after/ecuc-review.json",
            "pointer": observations["after"]["object_pointers"][0]
            if observations["after"]["object_pointers"]
            else "/objects",
        },
        "affected_objects": affected,
        "policy": policy,
        "observations": observations,
    }
