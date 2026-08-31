from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.review import run_review


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Review evaluation manifest requires non-empty {name}")
    return value


def _locator_key(artifact_id: str, locator: dict[str, Any]) -> str:
    return f"{artifact_id}\0{json.dumps(locator, sort_keys=True, separators=(',', ':'))}"


def load_evaluation_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != "review-evaluation-0.1":
        raise ValueError("Unsupported or missing review evaluation schema_version")
    _require_string(payload.get("evaluation_id"), "evaluation_id")
    repeat_runs = payload.get("repeat_runs", 3)
    if not isinstance(repeat_runs, int) or isinstance(repeat_runs, bool) or repeat_runs < 3:
        raise ValueError("Review evaluation repeat_runs must be at least three")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Review evaluation requires non-empty cases")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Review evaluation case must be an object")
        case_id = _require_string(case.get("case_id"), "case_id")
        if case_id in case_ids:
            raise ValueError(f"Duplicate review evaluation case_id: {case_id}")
        case_ids.add(case_id)
        _require_string(case.get("request"), "case request")
        if case.get("expected_status") not in {"answered", "partial", "refused"}:
            raise ValueError(f"Review evaluation case {case_id} has invalid expected_status")
        expected_checks = case.get("expected_checks")
        if not isinstance(expected_checks, dict) or not expected_checks:
            raise ValueError(f"Review evaluation case {case_id} requires expected_checks")
        if any(
            not isinstance(check_id, str)
            or status not in {"supported", "unsupported", "conflicted", "blocked"}
            for check_id, status in expected_checks.items()
        ):
            raise ValueError(f"Review evaluation case {case_id} has invalid check status")
        for field in ("expected_refusal_codes", "expected_findings", "gold_evidence_sets"):
            if not isinstance(case.get(field, []), list):
                raise ValueError(f"Review evaluation case {case_id} field {field} must be a list")
        if any(
            not isinstance(code, str) or not code
            for code in case.get("expected_refusal_codes", [])
        ):
            raise ValueError(f"Review evaluation case {case_id} has invalid refusal code")
        for evidence_set in case.get("gold_evidence_sets", []):
            if not isinstance(evidence_set, list) or not evidence_set:
                raise ValueError(f"Review evaluation case {case_id} has empty evidence set")
            for item in evidence_set:
                if not isinstance(item, dict) or set(item) != {"artifact_id", "locator"}:
                    raise ValueError(f"Review evaluation case {case_id} has invalid gold evidence")
                _require_string(item.get("artifact_id"), "gold artifact_id")
                locator = item.get("locator")
                if not isinstance(locator, dict) or locator.get("type") not in {
                    "json-pointer", "line-range"
                }:
                    raise ValueError(f"Review evaluation case {case_id} has invalid gold locator")
                if locator["type"] == "json-pointer":
                    if set(locator) != {"type", "pointer"} or not isinstance(
                        locator.get("pointer"), str
                    ):
                        raise ValueError(f"Review evaluation case {case_id} has invalid gold pointer")
                else:
                    start = locator.get("start_line")
                    end = locator.get("end_line")
                    if (
                        set(locator) != {"type", "start_line", "end_line"}
                        or not isinstance(start, int)
                        or isinstance(start, bool)
                        or not isinstance(end, int)
                        or isinstance(end, bool)
                        or not 1 <= start <= end
                    ):
                        raise ValueError(f"Review evaluation case {case_id} has invalid gold range")
    return payload


def _normalized_result(result: dict[str, Any], excluded: list[str]) -> dict[str, Any]:
    normalized = copy.deepcopy(result)
    for field in excluded:
        normalized.pop(field, None)
    return normalized


def render_evaluation_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Engineering Review Evaluation",
        "",
        f"- Evaluation: `{result['evaluation_id']}`",
        f"- Status: **{result['status']}**",
        f"- Cases: {result['case_count']}",
        f"- Repeat runs: {result['repeat_runs']}",
        "",
        "| Metric | Value | Gate |",
        "|---|---:|---:|",
        f"| Review status accuracy | {metrics['status_accuracy']:.3f} | 1.000 |",
        f"| Check-state accuracy | {metrics['check_state_accuracy']:.3f} | 1.000 |",
        f"| Conflict recall | {metrics['conflict_recall']:.3f} | 1.000 |",
        f"| False conflicts | {metrics['false_conflict_count']} | 0 |",
        f"| Citation validity | {metrics['citation_validity']:.3f} | 1.000 |",
        f"| Citation precision | {metrics['citation_precision']:.3f} | 1.000 |",
        f"| Evidence-set recall | {metrics['citation_evidence_set_recall']:.3f} | 1.000 |",
        f"| Refusal-code accuracy | {metrics['refusal_code_accuracy']:.3f} | 1.000 |",
        f"| Finding preservation | {metrics['finding_preservation']:.3f} | 1.000 |",
        f"| Repeatability | {metrics['repeatability']:.3f} | 1.000 |",
        "",
        "## Cases",
        "",
        "| Case | Passed | Observed status |",
        "|---|---:|---|",
    ]
    for case in result["cases"]:
        lines.append(
            f"| `{case['case_id']}` | {str(case['passed']).lower()} | {case['observed_status']} |"
        )
    lines.extend([
        "",
        "This evaluation uses checked-in gold locators and exact structural judgments. It does not use an LLM judge.",
        "",
    ])
    return "\n".join(lines)


def run_review_evaluation(manifest_path: Path, output: Path) -> dict[str, Any]:
    manifest = load_evaluation_manifest(manifest_path)
    repeat_runs = manifest.get("repeat_runs", 3)
    excluded = manifest.get("repeatability_excluded_fields", ["run_id", "started_at"])
    if not isinstance(excluded, list) or any(not isinstance(item, str) for item in excluded):
        raise ValueError("Review evaluation excluded fields must be strings")

    status_correct = 0
    check_correct = 0
    check_total = 0
    expected_conflicts = 0
    found_conflicts = 0
    false_conflicts = 0
    citation_count = 0
    valid_citations = 0
    gold_citation_count = 0
    evidence_set_cases = 0
    complete_evidence_set_cases = 0
    refusal_correct = 0
    finding_correct = 0
    repeatable_cases = 0
    case_results: list[dict[str, Any]] = []

    for case in manifest["cases"]:
        request_path = manifest_path.parent / case["request"]
        runs = [
            run_review(request_path, output / case["case_id"] / f"run-{index + 1}")
            for index in range(repeat_runs)
        ]
        result = runs[0]
        observed_checks = {
            item["check_id"]: item["status"] for item in result["checks"]
        }
        expected_checks = case["expected_checks"]
        case_status_correct = result["status"] == case["expected_status"]
        status_correct += int(case_status_correct)
        for check_id in sorted(set(expected_checks) | set(observed_checks)):
            expected_status = expected_checks.get(check_id)
            observed_status = observed_checks.get(check_id)
            check_total += 1
            correct = observed_status == expected_status
            check_correct += int(correct)
            if expected_status == "conflicted":
                expected_conflicts += 1
                found_conflicts += int(observed_status == "conflicted")
            elif observed_status == "conflicted":
                false_conflicts += 1

        citation_count += result["citation_validation"]["citation_count"]
        valid_citations += result["citation_validation"]["valid_count"]
        gold_sets = [
            {
                _locator_key(item["artifact_id"], item["locator"])
                for item in evidence_set
            }
            for evidence_set in case.get("gold_evidence_sets", [])
        ]
        gold_union = set().union(*gold_sets) if gold_sets else set()
        emitted = {
            _locator_key(item["artifact_id"], item["locator"])
            for item in result["citations"]
        }
        gold_citation_count += sum(
            _locator_key(item["artifact_id"], item["locator"]) in gold_union
            for item in result["citations"]
        )
        if gold_sets:
            evidence_set_cases += 1
            complete_evidence_set_cases += int(any(gold <= emitted for gold in gold_sets))

        observed_refusal_codes = sorted(
            item["code"] for item in result["refusal_reasons"]
        )
        refusal_match = observed_refusal_codes == sorted(
            case.get("expected_refusal_codes", [])
        )
        refusal_correct += int(refusal_match)
        finding_match = result["findings"] == case.get("expected_findings", [])
        finding_correct += int(finding_match)
        normalized_runs = [_normalized_result(item, excluded) for item in runs]
        repeatable = all(item == normalized_runs[0] for item in normalized_runs[1:])
        repeatable_cases += int(repeatable)

        case_passed = (
            case_status_correct
            and observed_checks == expected_checks
            and refusal_match
            and finding_match
            and result["citation_validation"]["status"] == "passed"
            and (not gold_sets or any(gold <= emitted for gold in gold_sets))
            and all(item in gold_union for item in emitted)
            and repeatable
        )
        case_results.append({
            "case_id": case["case_id"],
            "passed": case_passed,
            "observed_status": result["status"],
            "observed_checks": observed_checks,
            "observed_refusal_codes": observed_refusal_codes,
            "citation_count": len(result["citations"]),
            "repeatable": repeatable,
        })

    case_count = len(manifest["cases"])
    metrics = {
        "status_accuracy": status_correct / case_count,
        "check_state_accuracy": check_correct / check_total,
        "conflict_recall": found_conflicts / expected_conflicts if expected_conflicts else 1.0,
        "false_conflict_count": false_conflicts,
        "citation_validity": valid_citations / citation_count if citation_count else 1.0,
        "citation_precision": gold_citation_count / citation_count if citation_count else 1.0,
        "citation_evidence_set_recall": (
            complete_evidence_set_cases / evidence_set_cases if evidence_set_cases else 1.0
        ),
        "refusal_code_accuracy": refusal_correct / case_count,
        "finding_preservation": finding_correct / case_count,
        "repeatability": repeatable_cases / case_count,
    }
    gates_passed = (
        all(metrics[key] == 1.0 for key in (
            "status_accuracy",
            "check_state_accuracy",
            "conflict_recall",
            "citation_validity",
            "citation_precision",
            "citation_evidence_set_recall",
            "refusal_code_accuracy",
            "finding_preservation",
            "repeatability",
        ))
        and metrics["false_conflict_count"] == 0
        and all(item["passed"] for item in case_results)
    )
    timestamp = datetime.now(timezone.utc)
    evaluation = {
        "artifact_type": "engineering-review-evaluation",
        "schema_version": "review-evaluation-result-0.1",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "evaluation_id": manifest["evaluation_id"],
        "status": "passed" if gates_passed else "failed",
        "case_count": case_count,
        "repeat_runs": repeat_runs,
        "metrics": metrics,
        "cases": case_results,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "review-evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "review-evaluation.md").write_text(
        render_evaluation_markdown(evaluation), encoding="utf-8"
    )
    return evaluation
