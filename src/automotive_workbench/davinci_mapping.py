"""Read-only audit of explicit AUTOSAR sender/receiver signal mappings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from automotive_workbench.ecuc_project import xml


TYPES = {"SYSTEM-SIGNAL", "P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE", "VARIABLE-DATA-PROTOTYPE"}


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _ref(element: ET.Element, tag: str) -> str | None:
    node = element.find(f".//{{*}}{tag}")
    return node.text.strip() if node is not None and node.text else None


def _objects(root: ET.Element) -> dict[str, str]:
    found: dict[str, str] = {}

    def visit(node: ET.Element, path: tuple[str, ...]) -> None:
        name = node.findtext("{*}SHORT-NAME")
        current = (*path, name) if name else path
        if _tag(node) in TYPES and name:
            found["/" + "/".join(current)] = _tag(node)
        for child in node:
            if _tag(child) != "SHORT-NAME":
                visit(child, current)

    visit(root, ())
    return found


def summarize_mappings(sources: list[Path]) -> dict[str, object]:
    if not sources or len({p.resolve() for p in sources}) != len(sources):
        raise ValueError("Supply distinct ARXML sources")
    roots: list[ET.Element] = []
    inputs: list[dict[str, object]] = []
    objects: dict[str, str] = {}
    for source in sources:
        data = source.read_bytes()
        root = xml(data)
        roots.append(root)
        inputs.append({"path": str(source.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        for ref, kind in _objects(root).items():
            if ref in objects and objects[ref] != kind:
                raise ValueError(f"Conflicting object type: {ref}")
            objects[ref] = kind
    rows: list[dict[str, object]] = []
    for source_index, root in enumerate(roots):
        for mapping in root.findall(".//{*}SENDER-RECEIVER-TO-SIGNAL-MAPPING"):
            port = _ref(mapping, "CONTEXT-PORT-REF")
            element = _ref(mapping, "TARGET-DATA-PROTOTYPE-REF")
            signal = _ref(mapping, "SYSTEM-SIGNAL-REF")
            port_node = mapping.find(".//{*}CONTEXT-PORT-REF")
            direction = {"R-PORT-PROTOTYPE": "Rx", "P-PORT-PROTOTYPE": "Tx"}.get(
                (port_node.get("DEST") or "") if port_node is not None else "", "unknown"
            )
            refs = {"port": port, "data_element": element, "system_signal": signal}
            expected = {"port": {"Rx": "R-PORT-PROTOTYPE", "Tx": "P-PORT-PROTOTYPE"}.get(direction),
                        "data_element": "VARIABLE-DATA-PROTOTYPE", "system_signal": "SYSTEM-SIGNAL"}
            missing = [key for key, ref in refs.items() if ref is None or objects.get(ref) != expected[key]]
            rows.append({**refs, "source_index": source_index, "direction": direction,
                         "status": "resolved" if not missing else "attention-required",
                         "unresolved": missing})
    rows.sort(key=lambda row: (str(row["system_signal"]), str(row["port"])))
    result: dict[str, object] = {"contract_version": "davinci-mapping-audit-0.1",
                                 "status": "passed" if rows and all(row["status"] == "resolved" for row in rows) else "attention-required",
                                 "inputs": inputs,
                                 "mappings": rows, "summary": {"total": len(rows),
                                 "resolved": sum(row["status"] == "resolved" for row in rows)}}
    return result


def audit_mappings(sources: list[Path], output: Path) -> dict[str, object]:
    result = summarize_mappings(sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_mapping_audit(report_path: Path) -> dict[str, object]:
    stored = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or not isinstance(stored.get("inputs"), list):
        raise ValueError("Invalid mapping audit")
    paths = [row.get("path") if isinstance(row, dict) else None for row in stored["inputs"]]
    if not paths or any(not isinstance(path, str) for path in paths):
        raise ValueError("Invalid mapping sources")
    if stored != summarize_mappings([Path(cast(str, path)) for path in paths]):
        raise ValueError("Mapping audit does not match sources")
    return {"status": "passed", "verified": str(report_path)}
