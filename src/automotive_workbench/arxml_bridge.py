"""Offline, source-bound structural semantics for a pinned SWC ARXML subset.

This is not an AUTOSAR XSD validator or an ECUC importer. The supported vocabulary
comes from the public Generate-Arxml 4-3-0 export audited for P22.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

NS = "http://autosar.org/schema/r4.0"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
VERSION = "arxml-import-0.1"
MAX_BYTES = 4 * 1024 * 1024
NAMED = set(
    """AR-PACKAGE SW-BASE-TYPE IMPLEMENTATION-DATA-TYPE UNIT DATA-CONSTR
APPLICATION-PRIMITIVE-DATA-TYPE COMPU-METHOD APPLICATION-SW-COMPONENT-TYPE
R-PORT-PROTOTYPE P-PORT-PROTOTYPE SWC-INTERNAL-BEHAVIOR TIMING-EVENT RUNNABLE-ENTITY
VARIABLE-ACCESS DATA-TYPE-MAPPING-SET SENDER-RECEIVER-INTERFACE
VARIABLE-DATA-PROTOTYPE""".split()
)
REFS = {
    "BASE-TYPE-REF": {"SW-BASE-TYPE"},
    "COMPU-METHOD-REF": {"COMPU-METHOD"},
    "DATA-CONSTR-REF": {"DATA-CONSTR"},
    "DATA-ELEMENT-REF": {"VARIABLE-DATA-PROTOTYPE"},
    "REQUIRED-INTERFACE-TREF": {"SENDER-RECEIVER-INTERFACE"},
    "PROVIDED-INTERFACE-TREF": {"SENDER-RECEIVER-INTERFACE"},
    "DATA-TYPE-MAPPING-REF": {"DATA-TYPE-MAPPING-SET"},
    "START-ON-EVENT-REF": {"RUNNABLE-ENTITY"},
    "PORT-PROTOTYPE-REF": {"P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"},
    "TARGET-DATA-PROTOTYPE-REF": {"VARIABLE-DATA-PROTOTYPE"},
    "APPLICATION-DATA-TYPE-REF": {"APPLICATION-DATA-TYPE"},
    "IMPLEMENTATION-DATA-TYPE-REF": {"IMPLEMENTATION-DATA-TYPE"},
    "TYPE-TREF": {"APPLICATION-DATA-TYPE", "APPLICATION-PRIMITIVE-DATA-TYPE"},
}
SUPPORTED = (
    NAMED
    | set(REFS)
    | set(
        """AUTOSAR AR-PACKAGES ELEMENTS SHORT-NAME
CATEGORY SW-DATA-DEF-PROPS SW-DATA-DEF-PROPS-VARIANTS SW-DATA-DEF-PROPS-CONDITIONAL
SW-CALIBRATION-ACCESS BASE-TYPE-SIZE BASE-TYPE-ENCODING NATIVE-DECLARATION
TYPE-EMITTER DISPLAY-NAME FACTOR-SI-TO-UNIT OFFSET-SI-TO-UNIT DATA-CONSTR-RULES
DATA-CONSTR-RULE INTERNAL-CONSTRS LOWER-LIMIT UPPER-LIMIT PORTS REQUIRED-COM-SPECS
NONQUEUED-RECEIVER-COM-SPEC USES-END-TO-END-PROTECTION ALIVE-TIMEOUT ENABLE-UPDATE
FILTER DATA-FILTER-TYPE HANDLE-NEVER-RECEIVED INIT-VALUE APPLICATION-VALUE-SPECIFICATION
SW-VALUE-CONT SW-VALUES-PHYS V PROVIDED-COM-SPECS NONQUEUED-SENDER-COM-SPEC
INTERNAL-BEHAVIORS DATA-TYPE-MAPPING-REFS EVENTS PERIOD RUNNABLES
MINIMUM-START-INTERVAL CAN-BE-INVOKED-CONCURRENTLY DATA-RECEIVE-POINT-BY-ARGUMENTS
ACCESSED-VARIABLE AUTOSAR-VARIABLE-IREF DATA-SEND-POINTS SYMBOL
SUPPORTS-MULTIPLE-INSTANTIATION DATA-TYPE-MAPS DATA-TYPE-MAP IS-SERVICE DATA-ELEMENTS
""".split()
    )
)
BOUNDARIES = [
    "Structural values and reference integrity only; no XSD or full AUTOSAR validation.",
    "COM, IPdu, PduR and CanIf ECUC mapping unknown; no inferred BSW objects.",
    "No DaVinci import, RTE generation, runtime or physical ECU evidence.",
    "UUID and formatting are non-semantic; numeric text is not unit-normalized.",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_bytes(data: bytes, name: str, producer: dict[str, Any]) -> dict[str, Any]:
    if len(data) > MAX_BYTES:
        raise ValueError("ARXML exceeds 4 MiB subset limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("ARXML subset requires UTF-8") from exc
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I) or "\x00" in text:
        raise ValueError("DTD/entity declarations and NUL are unsupported")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid ARXML XML: {exc}") from exc
    if (
        root.tag != f"{{{NS}}}AUTOSAR"
        or root.get(f"{{{XSI}}}schemaLocation") != f"{NS} AUTOSAR_4-3-0.xsd"
    ):
        raise ValueError("ARXML subset requires r4.0 namespace and AUTOSAR_4-3-0.xsd")
    objects: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    unsupported: list[dict[str, str]] = []
    findings: list[dict[str, str]] = []
    inventory: Counter[str] = Counter()
    seen: dict[str, dict[str, Any]] = {}

    def finding(code: str, locator: str, message: str) -> None:
        findings.append(dict(code=code, locator=locator, message=message))

    def walk(
        node: ET.Element,
        locator: str,
        owner: dict[str, Any] | None,
        relative: str,
        depth: int,
    ) -> None:
        if depth > 64 or sum(inventory.values()) >= 20000:
            raise ValueError("ARXML exceeds depth/node subset limit")
        tag = node.tag.removeprefix(f"{{{NS}}}")
        inventory[tag] += 1
        known = node.tag == f"{{{NS}}}{tag}" and tag in SUPPORTED
        if not known:
            unsupported.append(dict(locator=locator, kind="element", name=node.tag))
        short = node.findall(f"{{{NS}}}SHORT-NAME")
        if tag in NAMED or short:
            if len(short) != 1 or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", short[0].text or ""
            ):
                finding(
                    "ARXML-IDENTITY", locator, "Expected exactly one valid SHORT-NAME"
                )
            else:
                identity = (owner["id"] if owner else "") + "/" + str(short[0].text)
                owner = dict(id=identity, kind=tag, locator=locator, facts=[])
                objects.append(owner)
                if identity in seen:
                    finding("ARXML-DUPLICATE", locator, identity)
                seen[identity] = owner
                relative = "."
        attributes = {k: v for k, v in sorted(node.attrib.items()) if k != "UUID"}
        allowed = {"UUID"}
        if tag in REFS:
            allowed.add("DEST")
        if tag in {"LOWER-LIMIT", "UPPER-LIMIT"}:
            allowed.add("INTERVAL-TYPE")
        if node is root:
            allowed.add(f"{{{XSI}}}schemaLocation")
        for attribute in sorted(set(node.attrib) - allowed):
            unsupported.append(
                dict(
                    locator=locator + "/@" + attribute, kind="attribute", name=attribute
                )
            )
        value = (node.text or "").strip()
        if owner is not None:
            owner["facts"].append(
                dict(path=relative, value=value, attributes=attributes)
            )
        elif value:
            unsupported.append(dict(locator=locator, kind="unowned-value", name=tag))
        if (node.tail or "").strip():
            unsupported.append(dict(locator=locator, kind="mixed-content", name=tag))
        if tag in REFS:
            references.append(
                dict(
                    owner=owner["id"] if owner else "",
                    locator=locator,
                    kind=tag,
                    target=value,
                    dest=node.get("DEST", ""),
                )
            )
        counts: Counter[str] = Counter()
        for child in node:
            child_tag = child.tag.removeprefix(f"{{{NS}}}")
            counts[child_tag] += 1
            segment = f"{child_tag}[{counts[child_tag]}]"
            walk(
                child,
                locator + "/" + segment,
                owner,
                relative + "/" + segment,
                depth + 1,
            )

    walk(root, "/AUTOSAR[1]", None, ".", 0)
    for ref in references:
        target = seen.get(ref["target"])
        if target is None:
            finding("ARXML-DANGLING-REF", ref["locator"], ref["target"])
        elif ref["dest"] not in REFS[ref["kind"]] or not (
            target["kind"] == ref["dest"]
            or (
                ref["dest"] == "APPLICATION-DATA-TYPE"
                and target["kind"] == "APPLICATION-PRIMITIVE-DATA-TYPE"
            )
        ):
            finding(
                "ARXML-DEST-MISMATCH",
                ref["locator"],
                f"{ref['dest']} -> {target['kind']}",
            )
    if not objects:
        finding("ARXML-EMPTY", "/AUTOSAR[1]", "No identifiable objects")
    for obj in objects:
        obj["facts"].sort(key=lambda fact: fact["path"])
    return dict(
        artifact_type="arxml-import",
        schema_version=VERSION,
        status="failed" if findings else "passed",
        coverage="partial" if unsupported else "supported-subset",
        autosar_version="4-3-0",
        namespace=NS,
        source=dict(
            name=name,
            sha256=digest(data),
            content_base64=base64.b64encode(data).decode("ascii"),
            producer=producer,
        ),
        inventory=dict(sorted(inventory.items())),
        objects=sorted(objects, key=lambda obj: (obj["id"], obj["locator"])),
        references=references,
        unsupported=unsupported,
        findings=findings,
        boundaries=BOUNDARIES,
    )


def import_arxml(path: Path, provenance: Path | None = None) -> dict[str, Any]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("ARXML exceeds 4 MiB subset limit")
    data = path.read_bytes()
    producer: dict[str, Any] = {"status": "unrecorded"}
    if provenance is not None:
        producer = json.loads(provenance.read_text(encoding="utf-8"))
        if not isinstance(producer, dict) or producer.get("arxml_sha256") != digest(
            data
        ):
            raise ValueError("Producer provenance ARXML hash mismatch")
    return import_bytes(data, path.name, producer)


def compare_imports(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    comparable = all(
        r["status"] == "passed" and r["coverage"] == "supported-subset"
        for r in [baseline, candidate]
    )
    changes = []
    if comparable:
        old = {o["id"]: o for o in baseline["objects"]}
        new = {o["id"]: o for o in candidate["objects"]}
        for identity in sorted(old.keys() | new.keys()):
            before, after = old.get(identity), new.get(identity)

            def semantic(o: dict[str, Any] | None) -> Any:
                return None if o is None else (o["kind"], o["facts"])

            if semantic(before) != semantic(after):
                changes.append(
                    dict(
                        id=identity,
                        change="added"
                        if before is None
                        else "removed"
                        if after is None
                        else "modified",
                        before=before,
                        after=after,
                    )
                )
    return dict(
        artifact_type="arxml-comparison",
        schema_version="arxml-comparison-0.1",
        status=("changed" if changes else "stable") if comparable else "not-comparable",
        baseline=baseline,
        candidate=candidate,
        changes=changes,
        source_bytes_changed=baseline["source"]["sha256"]
        != candidate["source"]["sha256"],
        boundaries=BOUNDARIES,
    )


def verify_report(report: dict[str, Any]) -> None:
    try:
        _verify_report(report)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed ARXML report structure") from exc


def _verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") == VERSION:
        source = report["source"]
        if len(source["content_base64"]) > 4 * ((MAX_BYTES + 2) // 3):
            raise ValueError("Embedded ARXML exceeds subset limit")
        try:
            data = base64.b64decode(source["content_base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid embedded ARXML snapshot") from exc
        expected = import_bytes(data, source["name"], source["producer"])
        if source["producer"].get("arxml_sha256", digest(data)) != digest(data):
            raise ValueError("Embedded producer hash mismatch")
    elif report.get("schema_version") == "arxml-comparison-0.1":
        verify_report(report["baseline"])
        verify_report(report["candidate"])
        expected = compare_imports(report["baseline"], report["candidate"])
    else:
        raise ValueError("Unknown ARXML report version")
    if report != expected:
        raise ValueError("ARXML report differs from embedded source replay")


def run_arxml(
    source: Path,
    output: Path,
    candidate: Path | None = None,
    provenance: Path | None = None,
) -> dict[str, Any]:
    report = import_arxml(source, provenance)
    if candidate is not None:
        report = compare_imports(report, import_arxml(candidate))
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("ARXML output must be empty or absent")
    output.mkdir(parents=True, exist_ok=True)
    (output / "arxml-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
