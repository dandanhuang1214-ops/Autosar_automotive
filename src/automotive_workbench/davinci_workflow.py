"""Combine independently verified DaVinci and ECUC evidence without inflating scope."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automotive_workbench.cfg_validation import verify_cfg_report
from automotive_workbench.davinci_mapping import verify_mapping_audit
from automotive_workbench.ecuc_communication import verify_communication
from automotive_workbench.ecuc_review import verify_review


def _read(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Workflow input must be a JSON object")
    return value, hashlib.sha256(data).hexdigest()


def summarize_workflow(mapping: Path, cfg: Path, communication: Path, review: Path) -> dict[str, object]:
    verify_mapping_audit(mapping)
    verify_cfg_report(cfg)
    verify_communication(communication)
    verify_review(review)
    mapping_data, mapping_sha = _read(mapping)
    cfg_data, cfg_sha = _read(cfg)
    communication_data, communication_sha = _read(communication)
    review_data, review_sha = _read(review)
    if mapping_data.get("contract_version") != "davinci-mapping-audit-0.1" or cfg_data.get("contract_version") != "cfg-validation-summary-0.1":
        raise ValueError("Unsupported DaVinci bridge contract")
    if communication_data.get("schema_version") != "ecuc-communication-0.1" or review_data.get("schema_version") != "ecuc-engineering-review-0.1":
        raise ValueError("Unsupported ECUC review contract")
    counts = cfg_data["validation_counts"]
    summary = review_data["summary"]
    layers = {
        "developer_mapping": {"status": mapping_data["status"], "total": mapping_data["summary"]["total"],
                              "resolved": mapping_data["summary"]["resolved"]},
        "ecuc_communication": {"status": communication_data["status"],
                               "paths": len(communication_data["paths"])},
        "ecuc_engineering": {"status": review_data["status"],
                             "structural_findings": summary["structural_findings"]},
        "cfg_validation": {"status": cfg_data["status"], "errors": counts["errors"],
                           "warnings": counts["warnings"],
                           "generation": cfg_data["generation"]["state"]},
        "can_bus_execution": {"status": "unassessed"},
    }
    paths = {"mapping": mapping, "cfg": cfg, "communication": communication, "review": review}
    hashes = {"mapping": mapping_sha, "cfg": cfg_sha, "communication": communication_sha, "review": review_sha}
    return {"contract_version": "davinci-workflow-assessment-0.1", "status": "attention-required"
            if any(layer["status"] in {"attention-required", "partial", "failed"} for layer in layers.values())
            else "scope-limited", "inputs": {key: {"path": str(path.resolve()), "sha256": hashes[key]}
                                                for key, path in paths.items()}, "layers": layers,
            "scope": "Read-only evidence correlation; no CFG generation, CAN bus or ECU execution claim"}


def assess_workflow(mapping: Path, cfg: Path, communication: Path, review: Path, output: Path) -> dict[str, object]:
    result = summarize_workflow(mapping, cfg, communication, review)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_workflow(report: Path) -> dict[str, object]:
    stored, _ = _read(report)
    inputs = stored.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"mapping", "cfg", "communication", "review"}:
        raise ValueError("Invalid workflow inputs")
    paths = []
    for key in ("mapping", "cfg", "communication", "review"):
        item = inputs[key]
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Invalid workflow input path")
        paths.append(Path(item["path"]))
    if stored != summarize_workflow(*paths):
        raise ValueError("Workflow assessment does not match inputs")
    return {"status": "passed", "verified": str(report)}
