from __future__ import annotations

import hashlib
import json
import os
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from automotive_workbench.project_review import STAGE_ORDER, load_project_report


STATUSES = {"passed", "failed", "blocked", "skipped"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _same(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right)
        )
    return left == right


def _pointer(value: Any, pointer: str) -> Any:
    target = value
    if pointer == "":
        return target
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must start with /")
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(target, list):
            target = target[int(token)]
        elif isinstance(target, dict):
            target = target[token]
        else:
            raise KeyError(token)
    return target


def _recorded_source(source: Path, output: Path) -> str:
    try:
        return Path(os.path.relpath(source, output)).as_posix()
    except ValueError:
        return str(source)


def _source(role: str, path: Path, output: Path) -> dict[str, str]:
    return {
        "role": role,
        "source": _recorded_source(path, output),
        "sha256": _sha256(path),
    }


def _reference(
    role: str,
    path: Path,
    pointer: str,
    value: Any,
    output: Path,
) -> dict[str, Any]:
    source_hash = _sha256(path)
    identity = f"{role}\0{source_hash}\0{pointer}".encode()
    return {
        "evidence_id": f"project-evidence-{hashlib.sha256(identity).hexdigest()[:24]}",
        "role": role,
        "source": _recorded_source(path, output),
        "source_sha256": source_hash,
        "pointer": pointer,
        "value": value,
    }


def _classify(baseline: str, candidate: str) -> str:
    if baseline == candidate:
        return "stable"
    if baseline == "passed" and candidate != "passed":
        return "regressed"
    if baseline != "passed" and candidate == "passed":
        return "improved"
    return "changed"


def _requirements(report: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    values = report.get("requirements")
    if not isinstance(values, list) or not values:
        raise ValueError("Project report requires non-empty requirements")
    items: dict[str, dict[str, Any]] = {}
    indexes: dict[str, int] = {}
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise ValueError("Project report requirement must be an object")
        requirement_id = item.get("id")
        if not isinstance(requirement_id, str) or not requirement_id:
            raise ValueError("Project report requirement requires an id")
        if requirement_id in items:
            raise ValueError(f"Duplicate project requirement id: {requirement_id}")
        if item.get("status") not in {"passed", "failed", "blocked"}:
            raise ValueError(f"Project requirement {requirement_id} has invalid status")
        if not isinstance(item.get("reason"), str) or not item["reason"]:
            raise ValueError(f"Project requirement {requirement_id} has invalid reason")
        items[requirement_id] = item
        indexes[requirement_id] = index
    return items, indexes


def _stage_file(report_path: Path, stage: dict[str, Any]) -> Path | None:
    value = stage.get("path")
    if value is None:
        return None
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("Project stage path must be a non-empty relative path or null")
    root = report_path.parent.resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Project stage path escapes the report directory") from exc
    return path


def _declared_stage_hash(report: dict[str, Any], stage_path: str) -> str:
    sources = report.get("source_artifacts")
    if not isinstance(sources, list):
        raise ValueError("project report source_artifacts are missing")
    normalized = stage_path.replace("\\", "/")
    matches = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if not isinstance(source, str):
            continue
        source = source.replace("\\", "/")
        if source == normalized or source.endswith(f"/{normalized}"):
            matches.append(item.get("sha256"))
    if len(matches) != 1:
        raise ValueError(f"stage hash declaration is not unique: {stage_path}")
    declared = matches[0]
    if (
        not isinstance(declared, str)
        or len(declared) != 64
        or any(character not in "0123456789abcdef" for character in declared)
    ):
        raise ValueError(f"stage hash declaration is invalid: {stage_path}")
    return declared


def _finding_records(
    role: str,
    report_path: Path,
    report: dict[str, Any],
    output: Path,
) -> tuple[dict[str, tuple[str, dict[str, Any], dict[str, Any]]], list[str]]:
    records: dict[str, tuple[str, dict[str, Any], dict[str, Any]]] = {}
    reasons: list[str] = []
    for stage_name in STAGE_ORDER:
        stage = report["stages"].get(stage_name)
        if stage is None:
            continue
        path = _stage_file(report_path, stage)
        if path is None:
            continue
        if not path.is_file():
            reasons.append(f"{role} stage artifact is missing: {stage_name}")
            continue
        try:
            declared_hash = _declared_stage_hash(report, stage["path"])
        except (KeyError, TypeError, ValueError) as exc:
            reasons.append(f"{role} stage artifact is unbound: {stage_name}: {exc}")
            continue
        if _sha256(path) != declared_hash:
            reasons.append(f"{role} stage artifact hash mismatch: {stage_name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            reasons.append(f"{role} stage artifact is invalid: {stage_name}: {exc}")
            continue
        findings = payload.get("findings", []) if isinstance(payload, dict) else []
        if not isinstance(findings, list):
            reasons.append(f"{role} stage findings are invalid: {stage_name}")
            continue
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                reasons.append(f"{role} finding is invalid: {stage_name}/{index}")
                continue
            comparable_finding = {
                key: value for key, value in finding.items()
                if key not in {"source", "source_artifact"}
            }
            fingerprint = json.dumps(
                {"stage": stage_name, "finding": comparable_finding},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            records[fingerprint] = (
                stage_name,
                finding,
                _reference(role, path, f"/findings/{index}", finding, output),
            )
    return records, reasons


def _all_references(result: dict[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for item in result.get("stages", []):
        references.extend(item.get("evidence", []))
    for item in result.get("requirements", []):
        references.extend(item.get("evidence", []))
    for item in result.get("findings", []):
        references.extend(item.get("evidence", []))
    return references


def _validate_references(path: Path, result: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    valid = 0
    seen: set[str] = set()
    for role in ("baseline", "candidate"):
        try:
            item = result[role]
            source = Path(item["source"])
            if not source.is_absolute():
                source = path.parent / source
            if _sha256(source) != item["sha256"]:
                raise ValueError(f"{role} report hash changed")
        except (OSError, KeyError, TypeError, ValueError) as exc:
            reasons.append(f"Invalid project comparison source: {exc}")
    for reference in _all_references(result):
        try:
            evidence_id = reference["evidence_id"]
            if evidence_id in seen:
                raise ValueError("duplicate evidence_id")
            source = Path(reference["source"])
            if not source.is_absolute():
                source = path.parent / source
            source_hash = _sha256(source)
            if source_hash != reference["source_sha256"]:
                raise ValueError("source hash changed")
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
            value = _pointer(payload, reference["pointer"])
            if not _same(value, reference["value"]):
                raise ValueError("referenced value changed")
            identity = (
                f"{reference['role']}\0{source_hash}\0{reference['pointer']}".encode()
            )
            expected_id = (
                f"project-evidence-{hashlib.sha256(identity).hexdigest()[:24]}"
            )
            if evidence_id != expected_id:
                raise ValueError("evidence_id does not match source and pointer")
        except (
            OSError,
            UnicodeError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            reasons.append(f"Invalid project comparison evidence: {exc}")
        else:
            seen.add(evidence_id)
            valid += 1
    count = len(_all_references(result))
    return {
        "status": "passed" if not reasons else "failed",
        "reference_count": count,
        "valid_count": valid,
        "reasons": reasons,
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Project Comparison",
        "",
        f"- Status: **{result['status']}**",
        f"- Baseline: `{result['baseline']['source']}`",
        f"- Candidate: `{result['candidate']['source']}`",
        f"- Evidence validation: **{result['evidence_validation']['status']}**",
        "",
    ]
    if result["basis"]["reasons"]:
        lines.extend(["## Not comparable", ""])
        lines.extend(f"- {reason}" for reason in result["basis"]["reasons"])
        return "\n".join([*lines, ""])
    lines.extend([
        "## Stage status",
        "",
        "| Stage | Baseline | Candidate | Classification |",
        "|---|---|---|---|",
    ])
    for item in result["stages"]:
        lines.append(
            f"| `{item['stage']}` | {item['baseline']} | {item['candidate']} | "
            f"{item['classification']} |"
        )
    lines.extend([
        "",
        "## Requirement status",
        "",
        "| Requirement | Baseline | Candidate | Classification |",
        "|---|---|---|---|",
    ])
    for item in result["requirements"]:
        lines.append(
            f"| `{item['id']}` | {item['baseline']['status']} "
            f"(`{item['baseline']['reason']}`) | {item['candidate']['status']} "
            f"(`{item['candidate']['reason']}`) | {item['classification']} |"
        )
    lines.extend(["", "## Finding delta", ""])
    if result["findings"]:
        for item in result["findings"]:
            finding = item["finding"]
            lines.append(
                f"- **{item['change']}** `{finding.get('severity', '')}` "
                f"`{finding.get('code', '')}` in `{item['stage']}`: "
                f"{finding.get('message', '')}"
            )
    else:
        lines.append("- No finding changes")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This comparison reports artifact differences. A regression identifies a "
        "worse declared project outcome; it does not by itself prove the engineering "
        "root cause or physical ECU behavior.",
        "",
    ])
    return "\n".join(lines)


def _render_html(result: dict[str, Any]) -> str:
    """Render a local, script-free view of the same comparison and its evidence."""
    def text(value: Any) -> str:
        return escape(str(value))

    def source_link(source: str) -> str:
        # Only relative local paths become links; encode URL punctuation, including
        # colons, so report content cannot introduce a URL scheme or fragment.
        if Path(source).is_absolute() or "\\" in source or ":" in source:
            return f"<code>{text(source)}</code>"
        return f'<a href="./{quote(source, safe="/")}">{text(source)}</a>'

    def evidence(references: list[dict[str, Any]]) -> str:
        entries = []
        for ref in references:
            entries.append(
                f"<li><strong>{text(ref['role'])}</strong> "
                f"{source_link(ref['source'])}<br>"
                f"JSON Pointer: <code>{text(ref['pointer'])}</code><br>"
                f"SHA-256: <code>{text(ref['source_sha256'])}</code>"
                f"<pre>{text(json.dumps(ref['value'], ensure_ascii=False, indent=2))}</pre></li>"
            )
        return (
            f"<details><summary>查看证据（{len(entries)}）</summary>"
            f"<ul>{''.join(entries)}</ul></details>"
        )

    labels = {
        "stable": "稳定", "regressed": "回归", "improved": "改善",
        "changed": "存在变化", "not-comparable": "不可比较",
    }
    status = result["status"]
    parts = [
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>项目回归比较</title><style>',
        'body{font:16px/1.6 system-ui,sans-serif;max-width:1100px;margin:auto;padding:24px;color:#172b40;background:#f6f8fb}',
        'h1,h2{line-height:1.3}section{background:white;padding:20px;margin:20px 0;border:1px solid #ccd5df;border-radius:8px}',
        'table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:10px;border-bottom:1px solid #ccd5df;vertical-align:top}',
        'code,pre{overflow-wrap:anywhere;white-space:pre-wrap}a{color:#0757a0}summary{cursor:pointer}li{margin:12px 0}.scroll{overflow-x:auto}',
        '</style><main><h1>项目回归比较</h1>',
        f"<p>结论：<strong>{text(labels[status])} / {text(status)}</strong></p>",
        '<p><a href="project-comparison.json">比较 JSON</a> · '
        '<a href="project-comparison.md">Markdown</a></p>',
        '<section><h2>比较来源与复验</h2>',
    ]
    for role in ("baseline", "candidate"):
        source = result[role]
        parts.append(
            f"<p><strong>{role}</strong>: {source_link(source['source'])}<br>"
            f"SHA-256: <code>{text(source['sha256'])}</code></p>"
        )
    validation = result["evidence_validation"]
    parts.extend([
        f"<p>生成时证据复验：<strong>{text(validation['status'])}</strong>；"
        f"引用 {validation['valid_count']} / {validation['reference_count']}。</p>",
        '<p>本页是生成时的静态快照。迁移或修改文件后，请重新执行独立复验；静态页面不会自动更新。</p>',
        '<pre>workbench verify-project-comparison &lt;比较目录&gt;/project-comparison.json</pre></section>',
    ])
    if result["basis"]["reasons"]:
        parts.append('<section><h2>不可比较的原因</h2><ul>')
        parts.extend(f"<li>{text(reason)}</li>" for reason in result["basis"]["reasons"])
        parts.append('</ul></section>')
    else:
        summary = result["summary"]
        parts.append(
            '<section><h2>变化概览</h2><p>'
            f"阶段变化 {summary['stage_change_count']}；验收项变化 {summary['requirement_change_count']}；"
            f"新增 finding {summary['finding_added_count']}；移除 finding {summary['finding_removed_count']}。"
            '</p></section>'
        )
        for key, title, identity in (
            ("stages", "阶段状态", "stage"),
            ("requirements", "声明验收项", "id"),
        ):
            parts.append(f'<section><h2>{title}</h2><div class="scroll"><table><thead><tr><th>条目</th><th>baseline</th><th>candidate</th><th>分类 / 证据</th></tr></thead><tbody>')
            for item in result[key]:
                values = [item[role] for role in ("baseline", "candidate")]
                if key == "requirements":
                    values = [f"{value['status']} — {value['reason']}" for value in values]
                parts.append(
                    f"<tr><th scope=\"row\">{text(item[identity])}</th>"
                    f"<td>{text(values[0])}</td><td>{text(values[1])}</td>"
                    f"<td>{text(item['classification'])}{evidence(item['evidence'])}</td></tr>"
                )
            parts.append('</tbody></table></div></section>')
        parts.append('<section><h2>Finding 变化</h2>')
        if not result["findings"]:
            parts.append('<p>没有 finding 变化。</p>')
        for item in result["findings"]:
            finding = item["finding"]
            parts.append(
                f"<h3>{text(item['change'])} · {text(item['stage'])} · {text(finding.get('code', ''))}</h3>"
                f"<p>{text(finding.get('severity', ''))}: {text(finding.get('message', ''))}</p>"
                f"{evidence(item['evidence'])}"
            )
        parts.append('</section>')
    parts.append('<section><h2>解释边界</h2><p>比较描述声明的项目结果与报告差异，不能单独证明工程根因或物理 ECU 行为。证据复验通过不等于候选项目验收通过。</p></section></main></html>')
    return "\n".join(parts) + "\n"


def _build_comparison(
    baseline_path: Path,
    candidate_path: Path,
    output: Path,
) -> dict[str, Any]:
    baseline = load_project_report(baseline_path)
    candidate = load_project_report(candidate_path)
    baseline_requirements, baseline_indexes = _requirements(baseline)
    candidate_requirements, candidate_indexes = _requirements(candidate)
    baseline_stages = set(baseline["stages"])
    candidate_stages = set(candidate["stages"])
    baseline_ids = set(baseline_requirements)
    candidate_ids = set(candidate_requirements)
    reasons: list[str] = []
    if baseline["schema_version"] != candidate["schema_version"]:
        reasons.append("project report schema_version differs")
    if baseline_stages != candidate_stages:
        reasons.append("project stage set differs")
    if baseline_ids != candidate_ids:
        reasons.append("project requirement id set differs")

    baseline_findings, baseline_finding_reasons = _finding_records(
        "baseline", baseline_path, baseline, output
    )
    candidate_findings, candidate_finding_reasons = _finding_records(
        "candidate", candidate_path, candidate, output
    )
    reasons.extend(baseline_finding_reasons)
    reasons.extend(candidate_finding_reasons)

    stage_results: list[dict[str, Any]] = []
    requirement_results: list[dict[str, Any]] = []
    finding_results: list[dict[str, Any]] = []
    if not reasons:
        for stage_name in sorted(baseline_stages, key=lambda item: STAGE_ORDER.index(item)):
            baseline_status = baseline["stages"][stage_name]["status"]
            candidate_status = candidate["stages"][stage_name]["status"]
            if baseline_status not in STATUSES or candidate_status not in STATUSES:
                raise ValueError(f"Invalid stage status: {stage_name}")
            pointer = f"/stages/{stage_name}/status"
            stage_results.append({
                "stage": stage_name,
                "baseline": baseline_status,
                "candidate": candidate_status,
                "classification": _classify(baseline_status, candidate_status),
                "evidence": [
                    _reference("baseline", baseline_path, pointer, baseline_status, output),
                    _reference("candidate", candidate_path, pointer, candidate_status, output),
                ],
            })
        for requirement_id in sorted(baseline_ids):
            baseline_item = baseline_requirements[requirement_id]
            candidate_item = candidate_requirements[requirement_id]
            baseline_index = baseline_indexes[requirement_id]
            candidate_index = candidate_indexes[requirement_id]
            baseline_status = baseline_item["status"]
            candidate_status = candidate_item["status"]
            classification = _classify(baseline_status, candidate_status)
            if (
                classification == "stable"
                and baseline_item["reason"] != candidate_item["reason"]
            ):
                classification = "changed"
            evidence = []
            for role, path, item, index in (
                ("baseline", baseline_path, baseline_item, baseline_index),
                ("candidate", candidate_path, candidate_item, candidate_index),
            ):
                for field in ("status", "reason"):
                    evidence.append(_reference(
                        role,
                        path,
                        f"/requirements/{index}/{field}",
                        item[field],
                        output,
                    ))
            requirement_results.append({
                "id": requirement_id,
                "baseline": {
                    "status": baseline_status,
                    "reason": baseline_item["reason"],
                },
                "candidate": {
                    "status": candidate_status,
                    "reason": candidate_item["reason"],
                },
                "classification": classification,
                "evidence": evidence,
            })
        for fingerprint in sorted(set(candidate_findings) - set(baseline_findings)):
            stage_name, finding, reference = candidate_findings[fingerprint]
            finding_results.append({
                "change": "added",
                "stage": stage_name,
                "finding": finding,
                "evidence": [reference],
            })
        for fingerprint in sorted(set(baseline_findings) - set(candidate_findings)):
            stage_name, finding, reference = baseline_findings[fingerprint]
            finding_results.append({
                "change": "removed",
                "stage": stage_name,
                "finding": finding,
                "evidence": [reference],
            })

    status = "not-comparable" if reasons else _classify(
        baseline["status"], candidate["status"]
    )
    if status == "stable" and any(
        item["classification"] != "stable"
        for item in [*stage_results, *requirement_results]
    ):
        status = "changed"
    if status == "stable" and finding_results:
        status = "changed"
    result: dict[str, Any] = {
        "artifact_type": "project-comparison",
        "schema_version": "project-comparison-0.1",
        "status": status,
        "baseline": _source("baseline", baseline_path, output),
        "candidate": _source("candidate", candidate_path, output),
        "basis": {
            "status": "not-comparable" if reasons else "matched",
            "stage_names": sorted(baseline_stages),
            "requirement_ids": sorted(baseline_ids),
            "reasons": reasons,
        },
        "stages": stage_results,
        "requirements": requirement_results,
        "findings": finding_results,
        "summary": {
            "stage_change_count": sum(
                item["classification"] != "stable" for item in stage_results
            ),
            "requirement_change_count": sum(
                item["classification"] != "stable" for item in requirement_results
            ),
            "finding_added_count": sum(
                item["change"] == "added" for item in finding_results
            ),
            "finding_removed_count": sum(
                item["change"] == "removed" for item in finding_results
            ),
        },
        "evidence_validation": {
            "status": "pending",
            "reference_count": 0,
            "valid_count": 0,
            "reasons": [],
        },
    }
    return result


def validate_project_comparison(path: Path) -> dict[str, Any]:
    """Recompute conclusions from local sources without writing or running labs."""
    validation: dict[str, Any] = {
        "status": "failed", "reference_count": 0, "valid_count": 0, "reasons": [],
    }
    try:
        path = path.resolve()
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(result, dict):
            raise ValueError("comparison must be an object")
        validation = _validate_references(path, result)
        sources = []
        for role in ("baseline", "candidate"):
            source = Path(result[role]["source"])
            sources.append((path.parent / source).resolve())
        expected = _build_comparison(sources[0], sources[1], path.parent)
        # The embedded validation is historical; always compute a fresh verdict.
        for key in sorted(expected.keys() - {"evidence_validation"}):
            if not _same(result.get(key), expected[key]):
                validation["reasons"].append(f"Comparison field differs from sources: {key}")
        if result.keys() != expected.keys():
            validation["reasons"].append("Comparison field set is invalid")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        validation["reasons"].append(f"Invalid project comparison: {exc}")
    validation["status"] = "failed" if validation["reasons"] else "passed"
    return validation


def compare_project_reports(
    baseline_path: Path,
    candidate_path: Path,
    output: Path,
) -> dict[str, Any]:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Project comparison output must be empty or absent")
    output = output.resolve()
    result = _build_comparison(baseline_path.resolve(), candidate_path.resolve(), output)
    if not output.exists():
        output.mkdir(parents=True)
    result_path = output / "project-comparison.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result["evidence_validation"] = validate_project_comparison(result_path)
    if result["evidence_validation"]["status"] == "failed":
        result["status"] = "not-comparable"
        result["basis"]["status"] = "not-comparable"
        result["basis"]["reasons"].append("comparison evidence validation failed")
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "project-comparison.md").write_text(
        _render_markdown(result), encoding="utf-8"
    )
    (output / "index.html").write_text(_render_html(result), encoding="utf-8")
    return result
