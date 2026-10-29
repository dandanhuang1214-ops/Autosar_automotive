"""Bounded, source-bound Developer SystemSignal to ECUC communication trace."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from automotive_workbench.davinci_mapping import verify_mapping_audit
from automotive_workbench.ecuc_communication import build_model
from automotive_workbench.ecuc_project import read_project, xml

VERSION = "cross-tool-trace-0.1"
FOREIGN_ROLE = "ComSystemTemplateSystemSignalRef"


def _tag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _system_links(root: ET.Element) -> dict[str, list[str]]:
    signals: dict[str, str] = {}
    mappings: dict[str, str] = {}

    def visit(node: ET.Element, path: tuple[str, ...]) -> None:
        name = node.findtext("{*}SHORT-NAME")
        current = (*path, name) if name else path
        ref = "/" + "/".join(current)
        if _tag(node) == "I-SIGNAL":
            target = node.findtext("{*}SYSTEM-SIGNAL-REF")
            if target:
                if ref in signals:
                    raise ValueError(f"Duplicate I-SIGNAL identity: {ref}")
                signals[ref] = target.strip()
        elif _tag(node) == "I-SIGNAL-TO-I-PDU-MAPPING":
            target = node.findtext("{*}I-SIGNAL-REF")
            if target:
                if ref in mappings:
                    raise ValueError(f"Duplicate I-PDU mapping identity: {ref}")
                mappings[ref] = target.strip()
        for child in node:
            if _tag(child) != "SHORT-NAME":
                visit(child, current)

    visit(root, ())
    linked: dict[str, list[str]] = defaultdict(list)
    for mapping_ref, signal_ref in mappings.items():
        system_ref = signals.get(signal_ref)
        if system_ref:
            linked[system_ref].append(mapping_ref)
    return {key: sorted(value) for key, value in linked.items()}


def summarize_trace(mapping_report: Path, system_arxml: Path, project: Path) -> dict[str, Any]:
    verify_mapping_audit(mapping_report)
    mapping_bytes = mapping_report.read_bytes()
    mapping = json.loads(mapping_bytes)
    system_bytes = system_arxml.read_bytes()
    system_refs = _system_links(xml(system_bytes))
    inspection, sources, containers = read_project(project)
    communication = build_model(inspection, sources, containers)
    by_foreign: dict[str, list[str]] = defaultdict(list)
    for container in containers:
        if container["type"] != "ComSignal":
            continue
        for ref in container["references"]:
            if ref["definition"].rsplit("/", 1)[-1] == FOREIGN_ROLE and not ref["conditional"]:
                by_foreign[ref["target"]].append(container["path"])
    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in communication["paths"]:
        for member in path["members"]:
            by_member[member["node"]].append(path)
    rows: list[dict[str, Any]] = []
    for item in mapping["mappings"]:
        signal = item["system_signal"]
        pdus = system_refs.get(signal, [])
        candidates = sorted({node for pdu in pdus for node in by_foreign[pdu]})
        paths = [(node, path) for node in candidates for path in by_member[node]]
        expected = {"Tx": "tx", "Rx": "rx"}.get(item["direction"])
        if item["status"] != "resolved":
            status, reason = "unassessed", "Developer mapping has unresolved references"
        elif not pdus:
            status, reason = "unassessed", "No explicit SystemSignal to I-PDU mapping"
        elif not candidates:
            status, reason = "unassessed", "No ECUC ComSignal foreign reference"
        elif len(paths) != 1:
            status, reason = "ambiguous", f"Expected one ECUC path; found {len(paths)}"
        elif paths[0][1]["direction"] != expected:
            status, reason = "direction-conflict", "Developer port and ECUC PDU directions differ"
        elif paths[0][1]["status"] != "resolved":
            status, reason = "partial", "ECUC path has unresolved links"
        else:
            status, reason = "resolved", "Exact explicit references and direction agree"
        chosen = paths[0][1] if len(paths) == 1 else None
        rows.append({"port": item["port"], "data_element": item["data_element"],
                     "system_signal": signal, "direction": item["direction"],
                     "i_pdu_mappings": pdus, "com_candidates": candidates,
                     "com_signal": paths[0][0] if chosen else None,
                     "com_ipdu": chosen["com_ipdu"] if chosen else None,
                     "pdur_route": chosen["route"] if chosen else None,
                     "canif_pdu": chosen["canif_pdu"] if chosen else None,
                     "status": status, "reason": reason})
    rows.sort(key=lambda row: (str(row["port"]), str(row["data_element"])))
    result_status = "resolved-in-scope" if rows and all(row["status"] == "resolved" for row in rows) else "attention-required"
    return {"contract_version": VERSION, "status": result_status,
            "inputs": {"mapping": {"path": str(mapping_report.resolve()), "sha256": hashlib.sha256(mapping_bytes).hexdigest()},
                       "system": {"path": str(system_arxml.resolve()), "sha256": hashlib.sha256(system_bytes).hexdigest()},
                       "project": {"path": str(project.resolve()), "sha256": hashlib.sha256(project.read_bytes()).hexdigest()}},
            "links": rows, "scope": "Exact SWC/SystemSignal/I-Signal/ComSignal/ComIPdu/PduR/CanIf references only; no runtime claim"}


def trace_cross_tool(mapping_report: Path, system_arxml: Path, project: Path, output: Path) -> dict[str, Any]:
    result = summarize_trace(mapping_report, system_arxml, project)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_trace(report: Path) -> dict[str, str]:
    stored = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or not isinstance(stored.get("inputs"), dict):
        raise ValueError("Invalid cross-tool trace")
    inputs = stored["inputs"]
    try:
        paths = [Path(inputs[key]["path"]) for key in ("mapping", "system", "project")]
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid cross-tool source paths") from exc
    if stored != summarize_trace(*paths):
        raise ValueError("Cross-tool trace does not match sources")
    return {"status": "passed", "verified": str(report)}


def summarize_impact(before: Path, after: Path) -> dict[str, Any]:
    verify_trace(before)
    verify_trace(after)
    old = json.loads(before.read_text(encoding="utf-8"))
    new = json.loads(after.read_text(encoding="utf-8"))
    def index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for row in report["links"]:
            key = (row["port"], row["data_element"])
            if key in result:
                raise ValueError("Duplicate Developer data-element identity")
            result[key] = row
        return result
    previous, current = index(old), index(new)
    fields = ("system_signal", "direction", "i_pdu_mappings", "com_candidates", "com_signal", "com_ipdu", "pdur_route", "canif_pdu", "status")
    changes = []
    for key in sorted(previous.keys() | current.keys()):
        left, right = previous.get(key), current.get(key)
        changed = [field for field in fields if left is None or right is None or left[field] != right[field]]
        if changed:
            changes.append({"port": key[0], "data_element": key[1],
                            "kind": "added" if left is None else "removed" if right is None else "changed",
                            "fields": changed})
    return {"contract_version": "cross-tool-impact-0.1", "status": "changed" if changes else "unchanged",
            "inputs": {"before": {"path": str(before.resolve()), "sha256": hashlib.sha256(before.read_bytes()).hexdigest()},
                       "after": {"path": str(after.resolve()), "sha256": hashlib.sha256(after.read_bytes()).hexdigest()}},
            "changes": changes}


def compare_traces(before: Path, after: Path, output: Path) -> dict[str, Any]:
    result = summarize_impact(before, after)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_impact(report: Path) -> dict[str, str]:
    stored = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or not isinstance(stored.get("inputs"), dict):
        raise ValueError("Invalid cross-tool impact")
    try:
        before = Path(stored["inputs"]["before"]["path"])
        after = Path(stored["inputs"]["after"]["path"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid cross-tool impact sources") from exc
    if stored != summarize_impact(before, after):
        raise ValueError("Cross-tool impact does not match sources")
    return {"status": "passed", "verified": str(report)}
