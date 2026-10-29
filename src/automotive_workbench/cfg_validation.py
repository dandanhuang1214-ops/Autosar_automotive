"""Source-bound, read-only summary of DaVinci CFG execution reports."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET


LIMIT = 64 * 1024 * 1024
SEVERITIES = {"FatalError": "fatalerrors", "Error": "errors", "Warning": "warnings",
              "Improvement": "improvements", "Info": "infos"}


def _parse(source: Path) -> tuple[ET.Element, bytes]:
    data = source.read_bytes()
    if len(data) > LIMIT:
        raise ValueError("CFG report exceeds 64 MiB")
    content = data.decode("utf-8-sig")
    if "\x00" in content or re.search(r"<!\s*(DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("DTD, entity declarations and NUL are unsupported")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid CFG report XML: {exc}") from exc
    if root.tag != "DaVinciExecutionReport":
        raise ValueError("Unsupported CFG report root")
    return root, data


def summarize_cfg_report(source: Path) -> dict[str, object]:
    root, data = _parse(source)
    validation = root.find("ValidationResults")
    if validation is None:
        raise ValueError("CFG report has no ValidationResults")
    declared: dict[str, int] = {}
    for key in SEVERITIES.values():
        value = validation.get(key)
        if value is None or not value.isdecimal():
            raise ValueError(f"Invalid declared {key} count")
        declared[key] = int(value)
    actual: Counter[str] = Counter()
    groups: list[dict[str, object]] = []
    for group in validation.findall("ValidationResultId"):
        counts: Counter[str] = Counter()
        for row in group.findall("ValidationResult"):
            severity = row.get("severity")
            if severity not in SEVERITIES:
                raise ValueError(f"Unsupported CFG severity: {severity}")
            key = SEVERITIES[severity]
            counts[key] += 1
            actual[key] += 1
        groups.append({"id": group.get("id"), "origin": group.get("origin"),
                       "message": group.get("message"), "counts": dict(sorted(counts.items()))})
    if any(actual[key] != declared[key] for key in SEVERITIES.values()):
        raise ValueError("CFG declared validation counts disagree with rows")
    generation = root.find("GenerationProcessResult")
    generation_state = generation.get("result") if generation is not None else "not-reported"
    generators: list[dict[str, str | None]] = []
    if generation is not None:
        for row in generation.findall("GenerationResult"):
            state = row.findtext("State")
            if state not in {"FAILED", "SUCCESSFUL", "NONE"}:
                raise ValueError(f"Unsupported CFG generator state: {state}")
            generators.append({"name": row.findtext("Name"), "state": state})
    if generation_state not in {"ERROR", "SUCCESSFUL", "not-reported"}:
        raise ValueError(f"Unsupported CFG generation state: {generation_state}")
    status = "attention-required" if declared["fatalerrors"] or declared["errors"] or generation_state == "ERROR" else "passed"
    return {"contract_version": "cfg-validation-summary-0.1", "status": status,
            "source": {"path": str(source.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
            "validation_counts": declared, "finding_groups": groups,
            "generation": {"state": generation_state, "generators": generators}}


def inspect_cfg_report(source: Path, output: Path) -> dict[str, object]:
    report = summarize_cfg_report(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def verify_cfg_report(report_path: Path) -> dict[str, object]:
    stored = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or not isinstance(stored.get("source"), dict):
        raise ValueError("Invalid CFG summary")
    source = stored["source"].get("path")
    if not isinstance(source, str):
        raise ValueError("Invalid CFG source path")
    if stored != summarize_cfg_report(Path(source)):
        raise ValueError("CFG summary does not match source")
    return {"status": "passed", "verified": str(report_path)}
