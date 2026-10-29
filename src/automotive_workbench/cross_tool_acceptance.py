"""Source-bound candidate acceptance reruns for exact cross-tool changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automotive_workbench.cross_tool_trace import verify_impact, verify_trace
from automotive_workbench.project_review import load_project_report

VERSION = "cross-tool-acceptance-impact-0.1"


def _read(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _pointer(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError("Evidence pointer must be absolute")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list) and token.isdecimal():
            value = value[int(token)]
        else:
            raise ValueError("Evidence pointer does not resolve")
    return value


def _evidence(requirement: dict[str, Any], report_path: Path) -> dict[str, Any]:
    evidence = requirement.get("evidence")
    if not isinstance(evidence, dict) or not all(isinstance(evidence.get(k), str) for k in ("path", "sha256", "pointer")):
        raise ValueError(f"Acceptance {requirement.get('id')} lacks source evidence")
    relative = Path(evidence["path"])
    root = report_path.parent.resolve()
    source = (root / relative).resolve()
    if relative.is_absolute() or not source.is_relative_to(root):
        raise ValueError("Acceptance evidence escapes report directory")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
        raise ValueError("Acceptance evidence hash mismatch")
    actual = _pointer(json.loads(raw), evidence["pointer"])
    if actual != requirement.get("actual"):
        raise ValueError("Acceptance actual value disagrees with evidence")
    return {"path": evidence["path"], "sha256": evidence["sha256"], "pointer": evidence["pointer"]}


def summarize_acceptance(impact_path: Path, bindings_path: Path, project_path: Path) -> dict[str, Any]:
    verify_impact(impact_path)
    impact, impact_sha = _read(impact_path)
    bindings, bindings_sha = _read(bindings_path)
    report = load_project_report(project_path)
    report_sha = hashlib.sha256(project_path.read_bytes()).hexdigest()
    if bindings.get("schema_version") != "cross-tool-acceptance-bindings-0.1" or bindings.get("project_name") != report["name"]:
        raise ValueError("Binding contract or project name mismatch")
    rows = bindings.get("links")
    if not isinstance(rows, list):
        raise ValueError("Bindings require links")
    before_path = Path(impact["inputs"]["before"]["path"])
    after_path = Path(impact["inputs"]["after"]["path"])
    verify_trace(before_path)
    verify_trace(after_path)
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    traces = [*before["links"], *after["links"]]
    allowed: dict[tuple[str, str], set[str]] = {}
    for row in traces:
        key = (row["port"], row["data_element"])
        if row["status"] == "resolved" and row["com_signal"]:
            allowed.setdefault(key, set()).add(row["com_signal"])
    requirements = {item["id"]: item for item in report["requirements"]}
    declared: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"port", "data_element", "com_signal", "acceptance_ids"}:
            raise ValueError("Invalid binding row")
        ids = row["acceptance_ids"]
        if not all(isinstance(row[field], str) and row[field] for field in ("port", "data_element", "com_signal")):
            raise ValueError("Binding identity invalid")
        key = (row["port"], row["data_element"])
        if (key in declared or row["com_signal"] not in allowed.get(key, set())
                or not isinstance(ids, list) or not ids
                or not all(isinstance(item, str) and item for item in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("Binding identity, ComSignal or IDs invalid")
        if any(item not in requirements for item in ids):
            raise ValueError("Binding references unknown acceptance ID")
        declared[key] = ids
    affected = []
    unbound = []
    for change in impact["changes"]:
        key = (change["port"], change["data_element"])
        if key not in declared:
            unbound.append({"port": key[0], "data_element": key[1], "reason": "No explicit acceptance binding"})
            continue
        checks = []
        for identity in sorted(declared[key]):
            item = requirements[identity]
            checks.append({"id": identity, "previous_status": item["status"],
                           "previous_evidence": _evidence(item, project_path),
                           "rerun_required": True})
        affected.append({"port": key[0], "data_element": key[1],
                         "change_fields": change["fields"], "acceptance": checks})
    return {"contract_version": VERSION,
            "status": "attention-required" if unbound else "rerun-required" if affected else "unchanged",
            "inputs": {"impact": {"path": str(impact_path.resolve()), "sha256": impact_sha},
                       "bindings": {"path": str(bindings_path.resolve()), "sha256": bindings_sha},
                       "project_report": {"path": str(project_path.resolve()), "sha256": report_sha}},
            "affected": affected, "unbound": unbound,
            "scope": "Explicitly declared candidate reruns; previous evidence does not prove post-change behavior"}


def assess_acceptance(impact: Path, bindings: Path, project_report: Path, output: Path) -> dict[str, Any]:
    result = summarize_acceptance(impact, bindings, project_report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_acceptance(report: Path) -> dict[str, str]:
    stored, _ = _read(report)
    inputs = stored.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Invalid acceptance impact inputs")
    try:
        paths = [Path(inputs[key]["path"]) for key in ("impact", "bindings", "project_report")]
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid acceptance impact paths") from exc
    if stored != summarize_acceptance(*paths):
        raise ValueError("Acceptance impact does not match sources")
    return {"status": "passed", "verified": str(report)}
