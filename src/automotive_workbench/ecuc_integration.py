"""Evidence-only application, task binding and mode-management checks."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

SW_TYPES = {
    "APPLICATION-SW-COMPONENT-TYPE",
    "SENSOR-ACTUATOR-SW-COMPONENT-TYPE",
    "SERVICE-SW-COMPONENT-TYPE",
    "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE",
    "ECU-ABSTRACTION-SW-COMPONENT-TYPE",
    "PARAMETER-SW-COMPONENT-TYPE",
}
EVENTS = {
    "TIMING-EVENT",
    "DATA-RECEIVED-EVENT",
    "INIT-EVENT",
    "OPERATION-INVOKED-EVENT",
    "MODE-SWITCH-EVENT",
    "SWC-MODE-SWITCH-EVENT",
    "BACKGROUND-EVENT",
    "EXTERNAL-TRIGGER-OCCURRED-EVENT",
}
BSW_EVENTS = {
    "BSW-TIMING-EVENT",
    "BSW-BACKGROUND-EVENT",
    "BSW-MODE-SWITCH-EVENT",
    "BSW-INTERNAL-TRIGGER-OCCURRED-EVENT",
}
# Module, owner, role -> target domain and supported object types.
RULES = {
    ("Rte", "RteSwComponentInstance", "RteSoftwareComponentInstanceRef"): (
        "application",
        {"SW-COMPONENT-PROTOTYPE"},
    ),
    ("Rte", "RteEventToTaskMapping", "RteEventRef"): ("application", EVENTS),
    ("Rte", "RteEventToTaskMapping", "RteMappedToTaskRef"): ("ecuc", {"OsTask"}),
    ("Rte", "RteBswEventToTaskMapping", "RteBswEventRef"): ("application", BSW_EVENTS),
    ("Rte", "RteBswEventToTaskMapping", "RteBswMappedToTaskRef"): ("ecuc", {"OsTask"}),
    ("Rte", "RteEventToTaskMapping", "RteUsedOsEventRef"): ("ecuc", {"OsEvent"}),
    ("Rte", "RteEventToTaskMapping", "RteUsedOsAlarmRef"): ("ecuc", {"OsAlarm"}),
    ("Rte", "RteEventToTaskMapping", "RteUsedOsSchTblExpiryPointRef"): (
        "ecuc",
        {"OsScheduleTableExpiryPoint"},
    ),
    ("Os", "OsTask", "OsTaskEventRef"): ("ecuc", {"OsEvent"}),
    ("Os", "OsApplication", "OsAppTaskRef"): ("ecuc", {"OsTask"}),
    ("BswM", "BswMRule", "BswMRuleExpressionRef"): ("ecuc", {"BswMLogicalExpression"}),
    ("BswM", "BswMRule", "BswMRuleTrueActionList"): ("ecuc", {"BswMActionList"}),
    ("BswM", "BswMRule", "BswMRuleFalseActionList"): ("ecuc", {"BswMActionList"}),
    ("BswM", "BswMLogicalExpression", "BswMArgumentRef"): (
        "ecuc",
        {"BswMLogicalExpression", "BswMModeCondition"},
    ),
    ("BswM", "BswMActionListItem", "BswMActionListItemRef"): (
        "ecuc",
        {"BswMAction", "BswMActionList", "BswMRule"},
    ),
}


def analyze(
    objects: list[dict[str, Any]], modules: dict[str, str], selected: list[str]
) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        by_id[obj["id"]].append(obj)
        by_path[obj["path"]].append(obj)
    app_roots = {
        o["path"]
        for o in objects
        if o["domain"] == "application"
        and o["type"] == "AR-PACKAGE"
        and not o["parent"]
    }
    edges: list[dict[str, Any]] = []
    refs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    findings = []

    def unique(identity: str) -> dict[str, Any] | None:
        return by_id[identity][0] if len(by_id[identity]) == 1 else None

    def finding(code: str, obj: dict[str, Any], message: str) -> None:
        findings.append(
            {
                "code": code,
                "severity": "WARNING",
                "object_id": obj["id"],
                "source": obj["source"],
                "message": message,
            }
        )

    for obj in objects:
        if len(by_id[obj["id"]]) > 1:
            finding(
                "INTEGRATION-AMBIGUOUS-OBJECT",
                obj,
                "Object identity has multiple definitions",
            )
        for reference in obj["references"]:
            role = reference["definition"].rsplit("/", 1)[-1]
            spec = RULES.get((modules.get(obj["module"], ""), obj["type"], role))
            if obj["domain"] == "application":
                if obj["type"] == "SW-COMPONENT-PROTOTYPE" and role == "TYPE-TREF":
                    spec = ("application", SW_TYPES | {"COMPOSITION-SW-COMPONENT-TYPE"})
                elif obj["type"] in EVENTS and role == "START-ON-EVENT-REF":
                    spec = ("application", {"RUNNABLE-ENTITY"})
                elif obj["type"] in BSW_EVENTS and role == "STARTS-ON-EVENT-REF":
                    spec = ("application", {"BSW-SCHEDULABLE-ENTITY"})
            target = reference["target"]
            candidates = [
                c for c in by_path[target] if not spec or c["domain"] == spec[0]
            ]
            match = candidates[0] if len(candidates) == 1 else None
            if not unique(obj["id"]) or len(candidates) > 1:
                status = "ambiguous"
            elif (
                obj["conditional"]
                or reference["conditional"]
                or (match and match["conditional"])
            ):
                status = "conditional"
            elif reference["kind"] not in {
                "ECUC-REFERENCE-VALUE",
                "application-reference",
            }:
                status = "unassessed"
            elif not target:
                status = "empty"
            elif (
                match
                and spec
                and (
                    match["type"] not in spec[1]
                    or (
                        match["domain"] == "ecuc"
                        and modules.get(match["module"])
                        != ("Os" if match["type"].startswith("Os") else "BswM")
                    )
                )
            ):
                status = "wrong-type"
            elif match:
                status = "resolved"
            elif spec and any(
                target == root or target.startswith(root + "/")
                for root in (selected if spec[0] == "ecuc" else app_roots)
            ):
                status = "missing"
            else:
                status = "unassessed"
            edge = {
                "id": f"dep-{len(edges):06d}",
                "consumer": obj["id"],
                "dependency": match["id"] if match and status == "resolved" else "",
                "target": target,
                "role": role,
                "kind": "reference",
                "source": reference["source"],
                "resolution": status,
                "assessment": "supported" if spec else "structural-only",
            }
            edges.append(edge)
            refs[(obj["id"], role)].append(edge)
            if spec and status != "resolved":
                finding("INTEGRATION-REFERENCE", obj, f"{role}: {status} ({target})")
        parent_id = obj["domain"] + ":" + obj["parent"]
        parent = unique(parent_id)
        if parent and unique(obj["id"]):
            edges.append(
                {
                    "id": f"dep-{len(edges):06d}",
                    "consumer": parent_id,
                    "dependency": obj["id"],
                    "target": obj["path"],
                    "role": "contains",
                    "kind": "containment",
                    "source": obj["source"],
                    "resolution": "conditional"
                    if parent["conditional"] or obj["conditional"]
                    else "resolved",
                    "assessment": "structural-only",
                }
            )

    def resolve(
        obj: dict[str, Any], role: str, gaps: list[str], *, many: bool = False
    ) -> list[dict[str, Any]]:
        candidates = refs[(obj["id"], role)]
        if not candidates or (not many and len(candidates) != 1):
            gaps.append(
                f"{role}: expected {'one or more' if many else 'one'}, found {len(candidates)}"
            )
        results = []
        for edge in candidates:
            if edge["resolution"] != "resolved":
                gaps.append(f"{role}: {edge['resolution']}")
            elif target := unique(edge["dependency"]):
                results.append(target)
        return results

    applications = []
    instances: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if (
            modules.get(obj["module"]) != "Rte"
            or obj["type"] != "RteSwComponentInstance"
        ):
            continue
        gaps: list[str] = []
        prototypes = resolve(obj, "RteSoftwareComponentInstanceRef", gaps)
        types = []
        for prototype in prototypes:
            parent = unique("application:" + prototype["parent"])
            if not parent or parent["type"] != "COMPOSITION-SW-COMPONENT-TYPE":
                gaps.append(
                    "Instance is not directly contained in a supplied composition"
                )
            types.extend(resolve(prototype, "TYPE-TREF", gaps))
        row = {
            "instance": obj["id"],
            "prototypes": [x["id"] for x in prototypes],
            "types": [x["id"] for x in types],
            "status": "partial" if gaps else "linked-in-scope",
            "gaps": gaps,
        }
        applications.append(row)
        instances[obj["id"]] = row
        if gaps:
            finding("APPLICATION-ASSOCIATION", obj, "; ".join(gaps))

    bindings = []
    for obj in objects:
        if modules.get(obj["module"]) != "Rte" or obj["type"] not in {
            "RteEventToTaskMapping",
            "RteBswEventToTaskMapping",
        }:
            continue
        bsw = obj["type"] == "RteBswEventToTaskMapping"
        gaps = []
        events = resolve(
            obj, "RteBswEventRef" if bsw else "RteEventRef", gaps, many=True
        )
        tasks = resolve(
            obj, "RteBswMappedToTaskRef" if bsw else "RteMappedToTaskRef", gaps
        )
        entities = []
        for event in events:
            event_entities = resolve(
                event, "STARTS-ON-EVENT-REF" if bsw else "START-ON-EVENT-REF", gaps
            )
            if any(event["parent"] != entity["parent"] for entity in event_entities):
                gaps.append(
                    "Event and runnable/schedulable entity have different internal-behavior owners"
                )
            entities.extend(event_entities)
        ancestor = unique("ecuc:" + obj["parent"])
        seen = set()
        while (
            ancestor
            and ancestor["id"] not in seen
            and ancestor["type"] != "RteSwComponentInstance"
        ):
            seen.add(ancestor["id"])
            ancestor = unique("ecuc:" + ancestor["parent"])
        instance = instances.get(ancestor["id"]) if ancestor and not bsw else None
        if not bsw:
            if not instance or instance["status"] != "linked-in-scope":
                gaps.append("Application instance/type association is unresolved")
            elif any(
                not any(
                    event["path"].startswith(t.removeprefix("application:") + "/")
                    for t in instance["types"]
                )
                for event in events
            ):
                gaps.append("Event does not belong to the referenced component type")
        for role in (
            "RteUsedOsEventRef",
            "RteUsedOsAlarmRef",
            "RteUsedOsSchTblExpiryPointRef",
        ):
            if refs[(obj["id"], role)]:
                resolve(obj, role, gaps)
        row = {
            "mapping": obj["id"],
            "instance": instance["instance"] if instance else "",
            "events": [x["id"] for x in events],
            "tasks": [x["id"] for x in tasks],
            "entities": [x["id"] for x in entities],
            "status": "partial" if gaps else "linked-in-scope",
            "gaps": sorted(set(gaps)),
            "schedule_validation": "unassessed",
            "reason": "Binding existence does not prove period, activation, priority, WCET or schedulability.",
        }
        bindings.append(row)
        if gaps:
            finding("SCHEDULE-BINDING-GAP", obj, "; ".join(row["gaps"]))

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["consumer"]].append(edge)
    modes = []
    for obj in objects:
        if modules.get(obj["module"]) != "BswM" or obj["type"] != "BswMRule":
            continue
        gaps = []
        resolve(obj, "BswMRuleExpressionRef", gaps)
        for role in ("BswMRuleTrueActionList", "BswMRuleFalseActionList"):
            if refs[(obj["id"], role)]:
                resolve(obj, role, gaps)
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(obj["id"], ())])
        visited: set[str] = set()
        while queue:
            current, trail = queue.popleft()
            if current in trail:
                gaps.append("Mode-management dependency cycle requires review")
                continue
            if current in visited:
                continue
            visited.add(current)
            if len(visited) > 10000:
                raise ValueError("Mode-management reachability exceeds 10000 objects")
            node = unique(current)
            if node and node["type"] == "BswMActionListItem":
                resolve(node, "BswMActionListItemRef", gaps)
            if node and node["type"] == "BswMLogicalExpression":
                resolve(node, "BswMArgumentRef", gaps, many=True)
            for edge in outgoing[current]:
                if edge["assessment"] != "supported" and edge["kind"] != "containment":
                    continue
                if edge["resolution"] != "resolved":
                    gaps.append(f"{edge['role']}: {edge['resolution']}")
                elif edge["dependency"].startswith("ecuc:"):
                    queue.append((edge["dependency"], (*trail, current)))
        # Kahn's algorithm also detects cycles reached through already-visited branches.
        links = [
            (e["consumer"], e["dependency"])
            for e in edges
            if e["consumer"] in visited
            and e["dependency"] in visited
            and e["resolution"] == "resolved"
            and (e["assessment"] == "supported" or e["kind"] == "containment")
        ]
        degree = {n: 0 for n in visited}
        for _, child in links:
            degree[child] += 1
        ready = deque(n for n in sorted(visited) if degree[n] == 0)
        removed = 0
        while ready:
            n = ready.popleft()
            removed += 1
            for parent, child in links:
                if parent == n:
                    degree[child] -= 1
                    if degree[child] == 0:
                        ready.append(child)
        if removed != len(visited):
            gaps.append("Mode-management dependency cycle requires review")
        modes.append(
            {
                "rule": obj["id"],
                "objects": sorted(visited),
                "status": "partial" if gaps else "linked-in-scope",
                "gaps": sorted(set(gaps)),
                "behavior_validation": "unassessed",
            }
        )
        if gaps:
            finding("MODE-STRUCTURE-GAP", obj, "; ".join(sorted(set(gaps))))
    return {
        "applications": applications,
        "bindings": bindings,
        "mode_rules": modes,
        "dependencies": edges,
        "findings": findings,
        "coverage": {
            "application": "provided" if app_roots else "unassessed",
            "task_bindings": "present" if bindings else "unassessed",
            "mode_rules": "present" if modes else "unassessed",
            "timing_and_runtime": "unassessed",
            "vendor_validation": "not-run",
        },
    }
