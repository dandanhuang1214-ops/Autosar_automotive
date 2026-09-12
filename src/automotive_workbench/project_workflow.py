"""Run the existing communication tools as one project acceptance workflow."""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from typing import Any

from automotive_workbench.adapters.canonical_contract import validate_contract_mapping
from automotive_workbench.adapters.dbc import validate_dbc_intent
from automotive_workbench.adapters.generation_gate import load_generation
from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    verify_evidence_bundle,
)


STAGES = {"canonical", "mapping", "communication"}


def load_project(path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw = path.read_bytes()
    project = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(project, dict):
        raise ValueError("Project must be an object")
    version = project.get("schema_version")
    keys = {"schema_version", "name", "inputs", "requirements"}
    if version == "workbench-project-0.2":
        keys.add("generation")
    if (
        not isinstance(version, str)
        or version not in {"workbench-project-0.1", "workbench-project-0.2"}
        or set(project) != keys
    ):
        raise ValueError("Project must use a closed workbench-project contract")
    if not isinstance(project["name"], str) or not project["name"].strip():
        raise ValueError("Project name must be non-empty")
    inputs = project["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"dbc", "contract", "intent"}:
        raise ValueError("Project requires dbc, contract and intent inputs")
    snapshots = {"project.json": raw}
    for key, value in inputs.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Project input paths must be non-empty strings")
        source = path.parent / value
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Project input must be a regular file: {key}")
        content = source.read_bytes()
        if key != "dbc":
            payload = json.loads(content.decode("utf-8-sig"))
            if not isinstance(payload, dict) or not isinstance(
                payload.get("signals"), list
            ):
                raise ValueError(
                    f"Project {key} requires a JSON object with a signals list"
                )
        snapshots[key + (".dbc" if key == "dbc" else ".json")] = content
    if "generation" in project:
        generated_sources, _ = load_generation(
            project["generation"], path.parent, snapshots["contract.json"]
        )
        snapshots.update(generated_sources)
    requirements = project["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Project requires at least one acceptance requirement")
    seen = set()
    for item in requirements:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "text",
            "stage",
            "pointer",
            "expected",
        }:
            raise ValueError(
                "Requirement must declare id, text, stage, pointer and expected"
            )
        for key in ("id", "text", "stage", "pointer"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"Requirement {key} must be non-empty")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", item["id"]) or item["id"] in seen:
            raise ValueError("Requirement IDs must be unique portable identifiers")
        seen.add(item["id"])
        if item["stage"] not in STAGES | (
            {"generation"} if "generation" in project else set()
        ):
            raise ValueError("Unknown requirement stage")
        if not item["pointer"].startswith("/") or re.search(
            r"~(?![01])", item["pointer"]
        ):
            raise ValueError("Requirement pointer must be an RFC 6901 JSON Pointer")
        expected = item["expected"]
        if type(expected) not in (str, int, float, bool, type(None)) or (
            isinstance(expected, float) and not math.isfinite(expected)
        ):
            raise ValueError("Requirement expected value must be a finite JSON scalar")
    return project, snapshots


def _pointer(document: Any, pointer: str) -> Any:
    value = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            value = value[int(token)]
        else:
            raise KeyError(pointer)
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _render_html(result: dict[str, Any]) -> str:
    def escape(value: Any) -> str:
        return html.escape(str(value), quote=True)

    rows = []
    for requirement in result["requirements"]:
        evidence = requirement["evidence"]
        link = (
            f'<a href="{escape(evidence["path"])}">{escape(evidence["pointer"])}</a>'
            if evidence
            else "—"
        )
        rows.append(
            f"<tr><td>{escape(requirement['id'])}</td><td>{escape(requirement['text'])}</td>"
            f"<td>{escape(requirement['status'])}</td><td>{escape(requirement['reason'])}</td>"
            f"<td>{escape(json.dumps(requirement['expected'], ensure_ascii=False))}</td>"
            f"<td>{escape(json.dumps(requirement['actual'], ensure_ascii=False))}</td><td>{link}</td></tr>"
        )
    stages = "".join(
        f"<li>{escape(name)}: <strong>{escape(stage['status'])}</strong>"
        + (
            f' · <a href="{escape(stage["path"])}">阶段报告</a>'
            if stage["path"]
            else ""
        )
        + "</li>"
        for name, stage in result["stages"].items()
    )
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(result['name'])}</title>"
        "<style>body{font:16px system-ui;margin:3rem auto;max-width:1200px;padding:0 1rem;"
        "color:#182638;background:#f7f9fc}table{border-collapse:collapse;width:100%;background:white}"
        "td,th{padding:.7rem;text-align:left;border:1px solid #ccd5df}a{color:#135ba1}"
        "strong{font-size:1.1em} .table{overflow:auto}</style>"
        f"<h1>{escape(result['name'])}</h1><p>项目验收：<strong>{escape(result['status'])}</strong></p>"
        "<h2>执行阶段</h2><ul>" + stages + "</ul><h2>声明的验收项</h2>"
        '<div class="table"><table><thead><tr><th>ID</th><th>验收要求</th><th>结果</th>'
        "<th>原因</th><th>期望</th><th>观测</th><th>证据</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
        '<p><a href="project-report.json">完整 JSON 与来源哈希</a> · '
        '<a href="../verification/evidence-bundle-verification.json">证据完整性复验</a></p>'
        "<p>仅验收项目文件中明确声明的条件；不代表完整需求覆盖率。"
        "通信实验验证所选 python-can 后端上的应用层行为，不证明目标 ECU 或量产配置。</p></html>"
    )


def run_project(project_path: Path, output: Path, config: BusConfig) -> dict[str, Any]:
    project, snapshots = load_project(project_path)
    if config.interface not in {"virtual", "socketcan"} or config.fd:
        raise ValueError(
            "Project communication supports classic virtual/socketcan only"
        )
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Project output must be an empty directory or absent")
    output = output.resolve()
    bundle = output / "bundle"
    inputs = bundle / "inputs"
    inputs.mkdir(parents=True)
    for name, raw in snapshots.items():
        (inputs / name).write_bytes(raw)
    dbc, contract, intent = (
        inputs / "dbc.dbc",
        inputs / "contract.json",
        inputs / "intent.json",
    )
    reports = {
        "canonical": validate_contract_mapping(dbc, contract, intent),
        "mapping": validate_dbc_intent(dbc, intent),
    }
    paths = {"canonical": "canonical.json", "mapping": "mapping.json"}
    if "generation" in project:
        # Reuse only the captured bytes, so changing original inputs after load cannot alter this run.
        declaration = {
            **project["generation"],
            "source_docx": "source.docx",
            "issue_report": "generation-issues.json",
        }
        _, reports["generation"] = load_generation(
            declaration, inputs, snapshots["contract.json"]
        )
        reports["generation"]["source_artifacts"] = [
            {"source": str(inputs / name), "sha256": sha256_file(inputs / name)}
            for name in (
                "project.json",
                "source.docx",
                "generation-issues.json",
                "contract.json",
            )
        ]
        reports = {"generation": reports["generation"], **reports}
        paths["generation"] = "generation.json"
    for name, stage_report in reports.items():
        _write_json(bundle / paths[name], stage_report)
    stages = {
        name: {"status": report["status"], "path": paths[name]}
        for name, report in reports.items()
    }
    if all(report["status"] == "passed" for report in reports.values()):
        reports["communication"] = run_communication_chain(
            dbc, intent, bundle / "communication", config
        )
        paths["communication"] = "communication/communication-evidence-report.json"
        stages["communication"] = {
            "status": reports["communication"]["status"],
            "path": paths["communication"],
        }
    else:
        stages["communication"] = {"status": "skipped", "path": None}
    requirements = []
    for item in project["requirements"]:
        stage = item["stage"]
        report = reports.get(stage)
        actual, evidence = None, None
        status, reason = "blocked", "stage_not_run"
        if report is not None:
            evidence = {
                "path": paths[stage],
                "sha256": sha256_file(bundle / paths[stage]),
                "pointer": item["pointer"],
            }
            if report["status"] == "blocked":
                reason = "backend_unavailable"
            else:
                try:
                    actual = _pointer(report, item["pointer"])
                    # JSON booleans must not compare equal to numbers.
                    same_type = type(actual) is type(item["expected"]) or (
                        type(actual) in (int, float)
                        and type(item["expected"]) in (int, float)
                    )
                    matched = same_type and actual == item["expected"]
                    status, reason = (
                        ("passed", "matched")
                        if matched
                        else ("failed", "value_mismatch")
                    )
                except (KeyError, IndexError):
                    status, reason = "failed", "evidence_missing"
        requirements.append(
            {
                **item,
                "status": status,
                "reason": reason,
                "actual": actual,
                "evidence": evidence,
            }
        )
    statuses = [s["status"] for s in stages.values()] + [
        r["status"] for r in requirements
    ]
    status = (
        "failed"
        if "failed" in statuses
        else "blocked"
        if "blocked" in statuses
        else "passed"
    )
    sources = [
        {"source": str(path), "sha256": sha256_file(path)}
        for path in sorted(inputs.iterdir())
    ]
    sources.extend(
        {"source": str(bundle / path), "sha256": sha256_file(bundle / path)}
        for path in paths.values()
    )
    result = {
        "artifact_type": "project-acceptance",
        "schema_version": "project-acceptance-0.2"
        if "generation" in project
        else "project-acceptance-0.1",
        "name": project["name"],
        "status": status,
        "stages": stages,
        "requirements": requirements,
        "source_artifacts": sources,
    }
    _write_json(bundle / "project-report.json", result)
    (bundle / "index.html").write_text(_render_html(result), encoding="utf-8")
    create_evidence_bundle_manifest(
        bundle, output / "manifest.json", "workbench run-project", base=output
    )
    verification = verify_evidence_bundle(
        bundle, output / "manifest.json", output / "verification", base=output
    )
    return {
        "status": status if verification["status"] == "passed" else "failed",
        "project_status": status,
        "integrity_status": verification["status"],
        "report": str(bundle / "index.html"),
        "report_json": str(bundle / "project-report.json"),
    }
