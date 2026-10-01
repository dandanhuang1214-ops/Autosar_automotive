"""Source-located object inventory for bounded ECUC integration and comparison."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

from automotive_workbench.ecuc_project import NS, child_text, local, sha, xml


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def owned_xml(node: ET.Element, *, root: bool = True) -> Any:
    """Keep unknown content and order; child objects own their content separately."""
    name = child_text(node, "SHORT-NAME")
    if name and not root:
        return ["object", local(node.tag), name]
    return [
        node.tag,
        sorted(node.attrib.items()),
        (node.text or "").strip(),
        (node.tail or "").strip(),
        [owned_xml(c, root=False) for c in node],
    ]


def opaque_xml(node: ET.Element, domain: str, *, root: bool = True) -> Any:
    if child_text(node, "SHORT-NAME") and not root:
        return None
    tag = local(node.tag)
    if domain == "ecuc" and not root and tag == "SUB-CONTAINERS":
        return None
    children = [opaque_xml(c, domain, root=False) for c in node]
    return [
        node.tag,
        sorted(node.attrib.items()),
        ""
        if (domain == "application" and not list(node))
        or tag in {"SHORT-NAME", "DEFINITION-REF", "VALUE", "VALUE-REF"}
        else (node.text or "").strip(),
        (node.tail or "").strip(),
        [c for c in children if c is not None],
    ]


def index_xml(data: bytes, file: str, domain: str) -> tuple[list[dict[str, Any]], str]:
    root = xml(data)
    objects: list[dict[str, Any]] = []

    def visit(
        node: ET.Element,
        path: str,
        xpath: str,
        parent: str,
        conditional: bool,
        depth: int,
    ) -> None:
        if depth > 200:
            raise ValueError("XML nesting exceeds supported depth")
        conditional = conditional or node.find(f"{{{NS}}}VARIATION-POINT") is not None
        name = child_text(node, "SHORT-NAME")
        if name:
            path += "/" + name
            objects.append(
                {
                    "path": path,
                    "type": local(node.tag),
                    "parent": parent,
                    "conditional": conditional,
                    "owned_sha256": sha(canonical(owned_xml(node)).encode()),
                    "opaque_sha256": sha(canonical(opaque_xml(node, domain)).encode()),
                    "source": {"file": file, "xpath": xpath, "object_path": path},
                    "_node": node,
                }
            )
            parent = path
        counts: Counter[str] = Counter()
        for child in node:
            counts[local(child.tag)] += 1
            visit(
                child,
                path,
                f"{xpath}/{local(child.tag)}[{counts[local(child.tag)]}]",
                parent,
                conditional,
                depth + 1,
            )

    visit(root, "", "/AUTOSAR[1]", "", False, 0)
    return objects, sha(canonical(owned_xml(root)).encode())


def application_objects(data: bytes, file: str) -> tuple[list[dict[str, Any]], str]:
    objects, residual = index_xml(data, file, "application")
    for obj in objects:
        node = obj.pop("_node")
        parameters: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def visit(
            n: ET.Element, xpath: str, conditional: bool, instance: bool = False
        ) -> None:
            if child_text(n, "SHORT-NAME"):
                return
            conditional = conditional or n.find(f"{{{NS}}}VARIATION-POINT") is not None
            tag = local(n.tag)
            instance = instance or tag.endswith("-IREF")
            source = {"file": file, "xpath": xpath, "object_path": obj["path"]}
            if not list(n) and tag != "SHORT-NAME":
                if tag.endswith("-REF") or tag.endswith("-TREF"):
                    references.append(
                        {
                            "definition": tag,
                            "target": (n.text or "").strip(),
                            "conditional": conditional,
                            "kind": "instance-reference"
                            if instance
                            else "application-reference",
                            "source": source,
                        }
                    )
                else:
                    parameters.append(
                        {
                            "definition": tag,
                            "value": (n.text or "").strip(),
                            "conditional": conditional,
                            "source": source,
                        }
                    )
            counts: Counter[str] = Counter()
            for c in n:
                counts[local(c.tag)] += 1
                visit(
                    c,
                    f"{xpath}/{local(c.tag)}[{counts[local(c.tag)]}]",
                    conditional,
                    instance,
                )

        counts: Counter[str] = Counter()
        for c in node:
            counts[local(c.tag)] += 1
            visit(
                c,
                f"{obj['source']['xpath']}/{local(c.tag)}[{counts[local(c.tag)]}]",
                obj["conditional"],
            )
        obj.update(
            {
                "id": "application:" + obj["path"],
                "domain": "application",
                "module": "",
                "definition": obj["type"],
                "parameters": parameters,
                "references": references,
            }
        )
    return objects, residual


def ecuc_objects(
    inspection: dict[str, Any],
    sources: dict[str, bytes],
    containers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    located: dict[tuple[str, str], dict[str, Any]] = {}
    residuals = {}
    known_locations = {(c["source"]["file"], c["source"]["xpath"]) for c in containers}
    known_locations.update(
        (m["source"]["file"], m["source"]["xpath"]) for m in inspection["modules"]
    )
    for source in inspection["sources"]:
        if source["role"] == "project":
            residuals["project/" + source["file"]] = sha(
                canonical(owned_xml(xml(sources[source["file"]], dpa=True))).encode()
            )
            continue
        items, residual = index_xml(sources[source["file"]], source["file"], "ecuc")
        residuals["project/" + source["file"]] = sha(
            canonical(
                [
                    residual,
                    sorted(
                        [
                            (x["path"], x["type"], x["owned_sha256"])
                            for x in items
                            if (source["file"], x["source"]["xpath"])
                            not in known_locations
                        ]
                    ),
                ]
            ).encode()
        )
        for item in items:
            located[(source["file"], item["source"]["xpath"])] = item
    objects = []
    for c in containers:
        item = located[(c["source"]["file"], c["source"]["xpath"])]
        objects.append(
            {
                "id": "ecuc:" + c["path"],
                "domain": "ecuc",
                **c,
                "opaque_sha256": item["opaque_sha256"],
                "owned_sha256": item["owned_sha256"],
            }
        )
    for m in inspection["modules"]:
        item = located[(m["source"]["file"], m["source"]["xpath"])]
        objects.append(
            {
                "id": "ecuc:" + m["path"],
                "domain": "ecuc",
                "path": m["path"],
                "module": m["path"],
                "type": "ECUC-MODULE-CONFIGURATION-VALUES",
                "definition": m["definition"],
                "parent": "",
                "conditional": item["conditional"],
                "parameters": [],
                "references": [],
                "source": m["source"],
                "opaque_sha256": item["opaque_sha256"],
                "owned_sha256": item["owned_sha256"],
            }
        )
    return objects, residuals


def semantic(obj: dict[str, Any]) -> dict[str, Any]:
    """Exclude file locations/formatting, retain all modeled and opaque content."""
    result = {
        key: obj[key]
        for key in (
            "type",
            "domain",
            "module",
            "definition",
            "parent",
            "conditional",
            "opaque_sha256",
        )
    }
    for key in ("parameters", "references"):
        result[key] = sorted(
            [{k: v for k, v in x.items() if k != "source"} for x in obj[key]],
            key=canonical,
        )
    return result


def prefix_sources(value: Any, prefix: str = "project/") -> Any:
    if isinstance(value, list):
        return [prefix_sources(x, prefix) for x in value]
    if isinstance(value, dict):
        return {
            k: prefix + v
            if k == "file" and isinstance(v, str)
            else prefix_sources(v, prefix)
            for k, v in value.items()
        }
    return value
