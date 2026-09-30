"""Read-only DPA/ECUC structural inspection, independent of the SWC ARXML subset."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath
from typing import Any

NS = "http://autosar.org/schema/r4.0"
VERSION = "ecuc-project-inspection-0.1"
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
BOUNDARIES = [
    "Selected ECUC structure only; no vendor XSD, parameter semantics or full AUTOSAR validation.",
    "External definitions and system/BSW references are unassessed, not assumed missing.",
    "No tool execution, code generation, compilation, physical ECU or source-identity evidence.",
]


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(node: ET.Element, tag: str) -> str:
    return node.findtext(f"{{{NS}}}{tag}", default="").strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_file(root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    if not normalized or PureWindowsPath(value).drive or normalized.startswith("/"):
        raise ValueError("Project files must use relative paths")
    path = root / normalized
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Project path escapes its root or is a symlink")
    return path.resolve()


def xml(data: bytes, *, dpa: bool = False) -> ET.Element:
    if len(data) > MAX_FILE:
        raise ValueError("XML exceeds the 64 MiB file limit")
    text = data.decode("utf-8-sig")
    if "\x00" in text or re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("DTD, entity declarations and NUL are unsupported")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid project XML: {exc}") from exc
    if root.tag != ("ProjectAssistant" if dpa else f"{{{NS}}}AUTOSAR"):
        raise ValueError("Unsupported project XML root or namespace")
    return root


def inspect(project: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    project = project.resolve()
    root = project.parent
    sources: dict[str, bytes] = {}
    inventory: list[dict[str, Any]] = []

    def load(value: str, role: str) -> tuple[ET.Element, str]:
        path = safe_file(root, value)
        name = path.relative_to(root).as_posix()
        if name not in sources:
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE or sum(map(len, sources.values())) + len(data) > MAX_TOTAL:
                raise ValueError("Project input size limit exceeded")
            sources[name] = data
            parsed = xml(data, dpa=role == "project")
            inventory.append({"file": name, "role": role, "sha256": sha(data), "bytes": len(data),
                              "schema_location": parsed.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "")})
        else:
            parsed = xml(sources[name], dpa=role == "project")
        return parsed, name

    dpa, _ = load(project.name, "project")
    config = dpa.findtext("EcucSplitter/Configuration", "").strip()
    collection, collection_file = load(config, "collection")
    collections = collection.findall(f".//{{{NS}}}ECUC-VALUE-COLLECTION")
    if len(collections) != 1:
        raise ValueError("Exactly one ECUC value collection is required")
    selected = [e.text.strip() if e.text else "" for e in collections[0].iter()
                if local(e.tag) == "ECUC-MODULE-CONFIGURATION-VALUES-REF"]
    if not selected or any(not p.startswith("/") for p in selected):
        raise ValueError("Collection must select absolute AUTOSAR module paths")
    modules: list[dict[str, Any]] = []
    locations: dict[str, list[dict[str, str]]] = defaultdict(list)
    containers: list[dict[str, Any]] = []
    parsed_files = {collection_file}

    def visit(node: ET.Element, file: str, path: str, xpath: str,
              module: str = "", depth: int = 0) -> None:
        if depth > 200:
            raise ValueError("XML nesting exceeds supported depth")
        name = child_text(node, "SHORT-NAME")
        if name:
            path += "/" + name
        tag = local(node.tag)
        if tag == "ECUC-MODULE-CONFIGURATION-VALUES":
            module = path
            modules.append({"path": path, "name": name, "definition": child_text(node, "DEFINITION-REF"),
                            "source": {"file": file, "xpath": xpath, "object_path": path}})
        if name and module in selected:
            locations[path].append({"file": file, "xpath": xpath, "object_path": path})
        if tag == "ECUC-CONTAINER-VALUE" and module in selected:
            refs = []
            for group_index, group in enumerate(node.findall(f"{{{NS}}}REFERENCE-VALUES"), 1):
                for i, ref in enumerate(group, 1):
                    # Instance references have different semantics; preserve them as unassessed.
                    refs.append({"definition": child_text(ref, "DEFINITION-REF"),
                                 "target": child_text(ref, "VALUE-REF"),
                                 "kind": local(ref.tag),
                                 "source": {"file": file, "object_path": path,
                                            "xpath": f"{xpath}/REFERENCE-VALUES[{group_index}]/{local(ref.tag)}[{sum(1 for previous in list(group)[:i] if previous.tag == ref.tag)}]"}})
            containers.append({"module": module, "path": path,
                               "type": child_text(node, "DEFINITION-REF").rsplit("/", 1)[-1],
                               "source": {"file": file, "xpath": xpath, "object_path": path}, "references": refs})
        counts: Counter[str] = Counter()
        for sub in node:
            counts[local(sub.tag)] += 1
            visit(sub, file, path, f"{xpath}/{local(sub.tag)}[{counts[local(sub.tag)]}]", module, depth + 1)

    visit(collection, collection_file, "", "/AUTOSAR[1]")
    for splitter in dpa.findall("EcucSplitter/Splitter"):
        name = splitter.get("File", "")
        normalized = safe_file(root, name).relative_to(root).as_posix()
        if normalized in parsed_files:
            continue
        tree, file = load(name, "module")
        parsed_files.add(file)
        visit(tree, file, "", "/AUTOSAR[1]")
    findings: list[dict[str, Any]] = []

    def finding(code: str, source: dict[str, str], message: str) -> None:
        findings.append({"code": code, "severity": "WARNING", "source": source, "message": message})

    collection_source = {"file": collection_file, "xpath": "/AUTOSAR[1]", "object_path": ""}
    for path, count in sorted(Counter(selected).items()):
        matches = [m for m in modules if m["path"] == path]
        if len(matches) != 1:
            finding("ECUC-MODULE-SELECTION", collection_source, f"Selected module {path} has {len(matches)} definitions")
        if count > 1:
            finding("ECUC-DUPLICATE-SELECTION", collection_source, f"Module {path} selected {count} times")
    for path, entries in sorted(locations.items()):
        if len(entries) > 1:
            for source in entries:
                finding("ECUC-AMBIGUOUS-PATH", source, f"Object {path} has {len(entries)} definitions")
    references: Counter[str] = Counter()
    for container in containers:
        for ref in container["references"]:
            target = ref["target"]
            if ref["kind"] != "ECUC-REFERENCE-VALUE":
                references["unassessed"] += 1
            elif not target:
                references["empty"] += 1
            elif target in locations:
                references["resolved" if len(locations[target]) == 1 else "ambiguous"] += 1
            elif any(target == m or target.startswith(m + "/") for m in selected):
                references["missing_selected_object"] += 1
                finding("ECUC-MISSING-REFERENCE", ref["source"], f"Selected-scope target not found: {target}")
            else:
                references["unassessed"] += 1
        if container["type"] in {"RteEventToTaskMapping", "RteBswEventToTaskMapping"}:
            key = "RteMappedToTaskRef" if container["type"] == "RteEventToTaskMapping" else "RteBswMappedToTaskRef"
            if not any(r["definition"].endswith("/" + key) and r["target"] for r in container["references"]):
                finding("ECUC-TASK-UNBOUND", container["source"], f"No non-empty {key}; event-to-task binding is unrecorded")
    active = [m for m in modules if m["path"] in selected]
    result_modules = []
    for module in active:
        counts = Counter(c["type"] for c in containers if c["module"] == module["path"])
        result_modules.append({**module, "container_counts": dict(sorted(counts.items()))})
    result = {"schema_version": VERSION, "status": "attention-required" if findings else "no-issues-in-scope",
              "project": project.name, "scope": BOUNDARIES, "sources": sorted(inventory, key=lambda x: x["file"]),
              "selected_modules": selected, "modules": result_modules,
              "unselected_module_paths": sorted({m["path"] for m in modules if m["path"] not in selected}),
              "references": {key: references[key] for key in ("resolved", "ambiguous", "missing_selected_object", "empty", "unassessed")},
              "findings": findings}
    return result, sources


def run_inspection(project: Path, output: Path) -> dict[str, Any]:
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Inspection output must be empty or absent, not a symlink")
    if output.resolve().is_relative_to(project.resolve().parent):
        raise ValueError("Inspection output must be outside the source project")
    result, sources = inspect(project)
    for name, data in sources.items():
        target = output / "snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "ecuc-inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_inspection(path: Path) -> dict[str, Any]:
    saved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or not isinstance(saved.get("project"), str):
        raise ValueError("Inspection must be an object with a project filename")
    if saved.get("schema_version") != VERSION:
        raise ValueError("Unsupported ECUC inspection version")
    snapshot = path.parent / "snapshot"
    if snapshot.is_symlink():
        raise ValueError("Snapshot root must not be a symlink")
    expected, sources = inspect(safe_file(snapshot, saved["project"]))
    actual = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()}
    if any(p.is_symlink() for p in snapshot.rglob("*")) or actual != set(sources):
        raise ValueError("Snapshot inventory differs")
    if json.dumps(saved, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("Saved inspection differs from replayed sources")
    return {"status": "passed", "schema_version": VERSION, "source_count": len(sources),
            "inspection_status": expected["status"]}
