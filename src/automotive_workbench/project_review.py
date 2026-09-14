from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from automotive_workbench.review import run_review


SUPPORTED_REPORT_VERSIONS = {
    "project-acceptance-0.1",
    "project-acceptance-0.2",
}
STAGE_ORDER = ("generation", "canonical", "mapping", "communication")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return normalized.upper() or "CHECK"


def _assertion_check(
    check_id: str,
    statement: str,
    artifact_id: str,
    pointer: str,
    expected: Any,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "statement": statement,
        "terms": [statement],
        "assertion": {
            "claim_key": check_id.casefold(),
            "operator": "equals",
            "expected": expected,
            "observations": [
                {
                    "artifact_id": artifact_id,
                    "locator": {"type": "json-pointer", "pointer": pointer},
                }
            ],
        },
    }


def load_project_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    if report.get("artifact_type") != "project-acceptance":
        raise ValueError("Project review requires a project-acceptance report")
    if report.get("schema_version") not in SUPPORTED_REPORT_VERSIONS:
        raise ValueError("Unsupported project-acceptance schema_version")
    if report.get("status") not in {"passed", "failed", "blocked"}:
        raise ValueError("Project report requires a valid status")
    if not isinstance(report.get("name"), str) or not report["name"]:
        raise ValueError("Project report requires a non-empty name")
    stages = report.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("Project report requires stages")
    return report


def _stage_source(report_path: Path, value: Any) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Project stage path must be a non-empty relative path or null")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("Project stage path must be relative to the project report")
    root = report_path.parent.resolve()
    source = (root / relative).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError("Project stage path escapes the report directory") from exc
    return source


def _artifact(
    artifact_id: str,
    artifact_type: str,
    source: Path,
    request_directory: Path,
) -> dict[str, str]:
    try:
        recorded_source = Path(os.path.relpath(source, request_directory)).as_posix()
    except ValueError:
        recorded_source = str(source)
    item = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "source": recorded_source,
        "confidentiality": "public",
    }
    if source.is_file():
        item["expected_sha256"] = _sha256(source)
    return item


def _render_project_review(result: dict[str, Any]) -> str:
    citations = {item["citation_id"]: item for item in result["citations"]}
    lines = [
        "# Project Engineering Review",
        "",
        result["question"],
        "",
        f"Status: **{result['status']}**; coverage: {result['coverage']:.3f}.",
        "",
        "## Evidence-backed checks",
        "",
    ]
    for check in result["checks"]:
        lines.append(f"- **{check['status']}** — {check['statement']}")
        for citation_id in check["citation_ids"]:
            citation = citations[citation_id]
            locator = citation["locator"]
            location = locator.get("pointer") or (
                f"lines {locator['start_line']}-{locator['end_line']}"
            )
            lines.append(
                f"  - `{citation['source']}#{location}`: `{citation['content']}`"
            )
    if result["refusal_reasons"]:
        lines.extend(["", "## Refusal reasons", ""])
        for reason in result["refusal_reasons"]:
            lines.append(f"- `{reason['code']}` — {reason['message']}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This review only states what the cited project artifacts support. It does "
        "not infer a physical ECU result, production readiness, or an unstated root cause.",
        "",
    ])
    return "\n".join(lines)


def run_project_review(
    report_path: Path,
    output: Path,
    claim: str | None = None,
) -> dict[str, Any]:
    """Review one project acceptance report with exact, validated citations."""
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Project review output must be empty or absent")
    if claim is not None and not claim.strip():
        raise ValueError("Project review claim must be non-empty")

    report_path = report_path.resolve()
    output = output.resolve()
    report = load_project_report(report_path)
    artifacts = [
        _artifact("project-report", "project-acceptance", report_path, output)
    ]
    artifact_ids = ["project-report"]
    checks: list[dict[str, Any]] = []
    stage_reports: dict[str, dict[str, Any]] = {}

    for stage_name in STAGE_ORDER:
        stage = report["stages"].get(stage_name)
        if stage is None:
            continue
        if not isinstance(stage, dict) or stage.get("status") not in {
            "passed", "failed", "blocked", "skipped"
        }:
            raise ValueError(f"Project report has invalid {stage_name} stage")
        source = _stage_source(report_path, stage.get("path"))
        if source is None:
            continue
        artifact_id = f"stage-{stage_name}"
        artifact_ids.append(artifact_id)
        artifacts.append(
            _artifact(artifact_id, f"{stage_name}-report", source, output)
        )
        if not source.is_file():
            continue
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            stage_reports[stage_name] = payload

    if claim is None:
        checks.append(_assertion_check(
            "PROJECT-STATUS",
            f"Project status is {report['status']}.",
            "project-report",
            "/status",
            report["status"],
        ))
        for stage_name in STAGE_ORDER:
            stage = report["stages"].get(stage_name)
            if stage is None:
                continue
            checks.append(_assertion_check(
                f"STAGE-{stage_name.upper()}",
                f"{stage_name} stage status is {stage['status']}.",
                "project-report",
                f"/stages/{stage_name}/status",
                stage["status"],
            ))
            artifact_id = f"stage-{stage_name}"
            stage_report = stage_reports.get(stage_name)
            if stage_report is None:
                continue
            findings = stage_report.get("findings", [])
            if not isinstance(findings, list):
                continue
            for index, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    continue
                for field in ("severity", "code", "message"):
                    value = finding.get(field)
                    if not isinstance(value, str) or not value:
                        continue
                    checks.append(_assertion_check(
                        _check_id(f"{stage_name}-finding-{index}-{field}"),
                        f"{stage_name} finding {index + 1} {field} is `{value}`.",
                        artifact_id,
                        f"/findings/{index}/{field}",
                        value,
                    ))
        requirements = report.get("requirements")
        if not isinstance(requirements, list):
            raise ValueError("Project report requires a requirements list")
        for index, requirement in enumerate(requirements):
            if not isinstance(requirement, dict):
                raise ValueError("Project report requirement must be an object")
            status = requirement.get("status")
            if status == "passed":
                continue
            requirement_id = requirement.get("id")
            reason = requirement.get("reason")
            if (
                not isinstance(requirement_id, str)
                or not requirement_id
                or status not in {"failed", "blocked"}
                or not isinstance(reason, str)
                or not reason
            ):
                raise ValueError("Project report has an invalid non-passing requirement")
            prefix = _check_id(f"requirement-{requirement_id}")
            checks.append(_assertion_check(
                f"{prefix}-STATUS",
                f"Requirement {requirement_id} status is {status}.",
                "project-report",
                f"/requirements/{index}/status",
                status,
            ))
            checks.append(_assertion_check(
                f"{prefix}-REASON",
                f"Requirement {requirement_id} reason is `{reason}`.",
                "project-report",
                f"/requirements/{index}/reason",
                reason,
            ))
        question = (
            f"What does the project evidence say about {report['name']}, which stages "
            "ran, and which recorded findings explain the result?"
        )
    else:
        checks.append({
            "check_id": "USER-CLAIM",
            "statement": claim.strip(),
            "terms": [claim.strip()],
        })
        question = f"Does the project evidence support this claim: {claim.strip()}"

    request = {
        "schema_version": "review-request-0.2",
        "request_id": f"project-review-{_check_id(report['name']).casefold()}",
        "question": question,
        "minimum_coverage": 1.0,
        "allowed_confidentiality": ["public"],
        "artifact_registry": artifacts,
        "artifact_ids": artifact_ids,
        "checks": checks,
    }
    if not output.exists():
        output.mkdir(parents=True)
    request_path = output / "review-request.json"
    request_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = run_review(request_path, output)
    (output / "project-review.md").write_text(
        _render_project_review(result), encoding="utf-8"
    )
    return result
