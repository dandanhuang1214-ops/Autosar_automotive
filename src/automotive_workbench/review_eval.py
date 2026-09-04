from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import BusConfig
from automotive_workbench.can_runtime import run_can_lab
from automotive_workbench.dtc_lifecycle import run_dtc_lifecycle
from automotive_workbench.review import run_review
from automotive_workbench.uds_runtime import run_uds_lab


_PRODUCERS = {
    "can-lab": (run_can_lab, "can-runtime-report.json"),
    "dtc-lifecycle": (run_dtc_lifecycle, "dtc-lifecycle-report.json"),
    "uds-lab": (run_uds_lab, "uds-lab-report.json"),
}
_PRODUCER_SOURCE = "${producer_report}"
_PRODUCER_INPUT = "${producer_input}"
_EXTERNAL_REPORT_PREFIX = "${external_report_"
_DYNAMIC_POINTER_TOKENS = {"run_id", "started_at", "duration_ms", "channel"}
_MUTABLE_POINTERS = {
    "can-lab": {
        "/scenarios/0/status",
        "/applicability_profile/software_version",
    },
    "dtc-lifecycle": {"/traces/2/observed_state"},
    "uds-lab": {"/scenarios/0/evidence/decoded_value"},
}


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Review evaluation manifest requires non-empty {name}")
    return value


def _locator_key(artifact_id: str, locator: dict[str, Any]) -> str:
    return f"{artifact_id}\0{json.dumps(locator, sort_keys=True, separators=(',', ':'))}"


def load_evaluation_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") not in {
        "review-evaluation-0.1", "review-evaluation-0.2", "review-evaluation-0.3",
        "review-evaluation-0.4",
        "review-evaluation-0.5",
        "review-evaluation-0.6",
        "review-evaluation-0.7",
        "review-evaluation-0.8",
        "review-evaluation-0.9",
        "review-evaluation-1.0",
    }:
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
        if payload["schema_version"] == "review-evaluation-0.1":
            case.setdefault("domain", "core")
        if payload["schema_version"] in {"review-evaluation-0.1", "review-evaluation-0.2"}:
            case.setdefault("split", "development")
        _require_string(case.get("domain"), "case domain")
        if case.get("split") not in {
            "development", "runtime", "held-out", "cross-run", "cohort"
        }:
            raise ValueError(f"Review evaluation case {case_id} has invalid split")
        _require_string(case.get("request"), "case request")
        producer = case.get("producer")
        external_reports = case.get("external_reports")
        if producer is not None and external_reports is not None:
            raise ValueError(
                f"Review evaluation case {case_id} cannot combine producer and external_reports"
            )
        if producer is not None:
            if not isinstance(producer, dict) or not {"kind", "input"} <= set(producer):
                raise ValueError(f"Review evaluation case {case_id} has invalid producer")
            if set(producer) - {"kind", "input", "runs", "mutations"}:
                raise ValueError(f"Review evaluation case {case_id} has invalid producer")
            if producer.get("kind") not in _PRODUCERS:
                raise ValueError(f"Review evaluation case {case_id} has unsupported producer")
            _require_string(producer.get("input"), "producer input")
            runs = producer.get("runs", 1)
            if not isinstance(runs, int) or isinstance(runs, bool) or runs not in {1, 2, 3}:
                raise ValueError(f"Review evaluation case {case_id} has invalid producer runs")
            if runs == 3 and payload["schema_version"] not in {
                "review-evaluation-0.7", "review-evaluation-0.8",
                "review-evaluation-0.9",
                "review-evaluation-1.0",
            }:
                raise ValueError(
                    f"Review evaluation case {case_id} three-run producer requires schema 0.7 or newer"
                )
            mutations = producer.get("mutations", [])
            if not isinstance(mutations, list):
                raise ValueError(f"Review evaluation case {case_id} has invalid mutations")
            if (
                (runs != 1 or mutations)
                and payload["schema_version"] not in {
                    "review-evaluation-0.4", "review-evaluation-0.5",
                    "review-evaluation-0.6",
                    "review-evaluation-0.7",
                    "review-evaluation-0.8",
                    "review-evaluation-0.9",
                    "review-evaluation-1.0",
                }
            ):
                raise ValueError(
                    f"Review evaluation case {case_id} paired producer requires schema 0.4 or newer"
                )
            for mutation in mutations:
                if (
                    not isinstance(mutation, dict)
                    or set(mutation) != {"run", "pointer", "value"}
                    or mutation.get("run") not in range(1, runs + 1)
                    or mutation.get("pointer") not in _MUTABLE_POINTERS[producer["kind"]]
                    or isinstance(mutation.get("value"), (dict, list))
                ):
                    raise ValueError(
                        f"Review evaluation case {case_id} has unsafe producer mutation"
                    )
        if external_reports is not None:
            if payload["schema_version"] not in {
                "review-evaluation-0.9", "review-evaluation-1.0"
            }:
                raise ValueError(
                    f"Review evaluation case {case_id} external_reports requires schema 0.9 or newer"
                )
            if not isinstance(external_reports, list) or not 1 <= len(external_reports) <= 3:
                raise ValueError(
                    f"Review evaluation case {case_id} requires one to three external_reports"
                )
            for report in external_reports:
                if not isinstance(report, dict) or set(report) != {
                    "source", "expected_sha256"
                }:
                    raise ValueError(
                        f"Review evaluation case {case_id} has invalid external report"
                    )
                _require_string(report.get("source"), "external report source")
                digest = report.get("expected_sha256")
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                ):
                    raise ValueError(
                        f"Review evaluation case {case_id} has invalid external report SHA-256"
                    )
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
        expected_drift_catalog = case.get("expected_drift_catalog", [])
        if not isinstance(expected_drift_catalog, list):
            raise ValueError(
                f"Review evaluation case {case_id} expected_drift_catalog must be a list"
            )
        for item in expected_drift_catalog:
            if (
                not isinstance(item, dict)
                or set(item) != {
                    "check_id", "claim_key", "baseline_artifact_id",
                    "candidate_artifact_id", "status",
                }
                or any(
                    not isinstance(item.get(field), str) or not item[field]
                    for field in (
                        "check_id", "claim_key", "baseline_artifact_id",
                        "candidate_artifact_id",
                    )
                )
                or item.get("status") not in {
                    "stable", "drifted", "not-comparable"
                }
            ):
                raise ValueError(
                    f"Review evaluation case {case_id} has invalid expected_drift_catalog"
                )
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pointer_tokens(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        return []
    return [
        item.replace("~1", "/").replace("~0", "~")
        for item in pointer[1:].split("/")
    ]


def _set_pointer(payload: Any, pointer: str, value: Any) -> None:
    tokens = _pointer_tokens(pointer)
    if not tokens:
        raise ValueError("Producer mutation requires a non-root JSON Pointer")
    target = payload
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    final = tokens[-1]
    if isinstance(target, list):
        target[int(final)] = value
    else:
        if final not in target:
            raise ValueError(f"Producer mutation pointer does not exist: {pointer}")
        target[final] = value


def _validate_comparable_observations(request: dict[str, Any]) -> None:
    paired_ids = {
        artifact["artifact_id"]
        for artifact in request.get("artifact_registry", [])
        if isinstance(artifact.get("source"), str)
        and (
            artifact["source"].startswith("${producer_report_")
            or artifact["source"].startswith(_EXTERNAL_REPORT_PREFIX)
        )
    }
    for check in request.get("checks", []):
        for observation in check.get("assertion", {}).get("observations", []):
            locator = observation.get("locator", {})
            if observation.get("artifact_id") not in paired_ids:
                continue
            if locator.get("type") != "json-pointer":
                continue
            pointer = locator.get("pointer", "")
            if _DYNAMIC_POINTER_TOKENS & set(_pointer_tokens(pointer)):
                raise ValueError(
                    f"Review evaluation dynamic field is not comparable: {pointer}"
                )


def _materialize_request(
    manifest_path: Path,
    manifest_version: str,
    case: dict[str, Any],
    case_output: Path,
) -> tuple[Path, dict[str, Any]]:
    request_path = manifest_path.parent / case["request"]
    producer = case.get("producer")
    external_reports = case.get("external_reports")
    if producer is None and external_reports is None:
        return request_path, {}

    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    _validate_comparable_observations(request)
    if external_reports is not None:
        report_paths: list[Path] = []
        reports: list[dict[str, Any]] = []
        for index, report_spec in enumerate(external_reports, 1):
            report_path = (manifest_path.parent / report_spec["source"]).resolve()
            if not report_path.is_file():
                raise ValueError(
                    f"Review evaluation external report does not exist: {report_path}"
                )
            actual_sha256 = _sha256(report_path)
            if actual_sha256 != report_spec["expected_sha256"]:
                raise ValueError(
                    f"Review evaluation external report SHA-256 mismatch: {report_path}"
                )
            try:
                report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"Review evaluation external report is not valid JSON: {report_path}"
                ) from error
            applicability_profile = report.get("applicability_profile")
            _validate_applicability_profile(
                applicability_profile, f"external report {index}"
            )
            ci_provenance = report.get("ci_provenance")
            if manifest_version == "review-evaluation-1.0":
                _validate_ci_provenance(ci_provenance, f"external report {index}")
            report_paths.append(report_path)
            report_evidence = {
                "report": report_spec["source"],
                "source_sha256": actual_sha256,
                "status": "verified",
                "applicability_profile": copy.deepcopy(applicability_profile),
            }
            if ci_provenance is not None:
                report_evidence["ci_provenance"] = {
                    **copy.deepcopy(ci_provenance),
                    "status": "hash-bound",
                }
            reports.append(report_evidence)

        placeholders = {
            f"${{external_report_{index}}}": index - 1
            for index in range(1, len(report_paths) + 1)
        }
        substitutions = _substitute_report_artifacts(
            request, placeholders, report_paths, reports
        )
        if substitutions != len(report_paths):
            raise ValueError(
                f"Review evaluation external report case {case['case_id']} requires "
                f"{len(report_paths)} external report artifact(s)"
            )
        materialized = _write_materialized_request(case_output, request)
        return materialized, {
            "external_reports": {
                "status": "verified",
                "report_count": len(reports),
                "reports": reports,
            }
        }

    producer_output = case_output / "producer"
    producer_input = (manifest_path.parent / producer["input"]).resolve()
    kind = producer["kind"]
    runner, report_name = _PRODUCERS[kind]
    producer_runs = producer.get("runs", 1)
    mutations_by_run: dict[int, list[dict[str, Any]]] = {}
    for mutation in producer.get("mutations", []):
        mutations_by_run.setdefault(mutation["run"], []).append(mutation)
    reports: list[dict[str, Any]] = []
    report_paths: list[Path] = []
    for run_number in range(1, producer_runs + 1):
        run_output = (
            producer_output if producer_runs == 1 else producer_output / f"run-{run_number}"
        )
        if kind == "uds-lab":
            produced = runner(
                producer_input, BusConfig("virtual", "workbench"), run_output
            )
        else:
            produced = runner(producer_input, run_output)
        report_path = run_output / report_name
        if produced.get("status") != "passed" or not report_path.is_file():
            raise RuntimeError(
                f"Review evaluation producer {kind} run {run_number} did not "
                "produce a passed report"
            )
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        if mutations_by_run.get(run_number):
            for mutation in mutations_by_run[run_number]:
                _set_pointer(report, mutation["pointer"], mutation["value"])
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        applicability_profile = report.get("applicability_profile")
        _validate_applicability_profile(applicability_profile, f"producer {kind}")
        report_paths.append(report_path)
        reports.append(
            {
                "report": (
                    report_name
                    if producer_runs == 1
                    else f"run-{run_number}/{report_name}"
                ),
                "source_sha256": _sha256(report_path),
                "status": produced["status"],
                "applicability_profile": copy.deepcopy(applicability_profile),
            }
        )

    placeholders = (
        {_PRODUCER_SOURCE: 0}
        if producer_runs == 1
        else {
            f"${{producer_report_{index}}}": index - 1
            for index in range(1, producer_runs + 1)
        }
    )
    substitutions = _substitute_report_artifacts(
        request, placeholders, report_paths, reports
    )
    if substitutions != producer_runs:
        raise ValueError(
            f"Review evaluation producer case {case['case_id']} requires "
            f"{producer_runs} producer report artifact(s)"
        )
    materialized = _write_materialized_request(case_output, request)
    evidence: dict[str, Any] = {"kind": kind, "status": "passed"}
    if producer_runs == 1:
        evidence.update(reports[0])
    else:
        evidence.update({"runs": producer_runs, "reports": reports})
        if producer.get("mutations"):
            evidence["mutations"] = copy.deepcopy(producer["mutations"])
    return materialized, {"producer": evidence}


def _validate_applicability_profile(profile: Any, source: str) -> None:
    if (
        not isinstance(profile, dict)
        or set(profile) != {
            "variant", "software_version", "calibration_version", "backend"
        }
        or any(not isinstance(value, str) or not value for value in profile.values())
    ):
        raise ValueError(
            f"Review evaluation {source} emitted invalid applicability_profile"
        )


def _validate_ci_provenance(provenance: Any, source: str) -> None:
    if (
        not isinstance(provenance, dict)
        or set(provenance) != {
            "provider", "repository", "run_id", "job_id", "commit_sha"
        }
        or any(not isinstance(value, str) or not value for value in provenance.values())
        or len(provenance["commit_sha"]) not in {40, 64}
        or any(
            character not in "0123456789abcdef"
            for character in provenance["commit_sha"]
        )
    ):
        raise ValueError(f"Review evaluation {source} emitted invalid ci_provenance")


def _substitute_report_artifacts(
    request: dict[str, Any],
    placeholders: dict[str, int],
    report_paths: list[Path],
    reports: list[dict[str, Any]],
) -> int:
    substitutions = 0
    for artifact in request.get("artifact_registry", []):
        index = placeholders.get(artifact.get("source"))
        if index is not None:
            artifact["source"] = str(report_paths[index].resolve())
            artifact["expected_sha256"] = reports[index]["source_sha256"]
            substitutions += 1
    return substitutions


def _write_materialized_request(case_output: Path, request: dict[str, Any]) -> Path:
    materialized = case_output / "materialized-request.json"
    materialized.parent.mkdir(parents=True, exist_ok=True)
    materialized.write_text(
        json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return materialized


def _normalized_result(result: dict[str, Any], excluded: list[str]) -> dict[str, Any]:
    normalized = copy.deepcopy(result)
    for field in excluded:
        normalized.pop(field, None)
    return normalized


def _expected_findings(
    case: dict[str, Any], manifest_path: Path
) -> list[dict[str, Any]]:
    expected = copy.deepcopy(case.get("expected_findings", []))
    producer = case.get("producer")
    if producer is None:
        return expected
    source = str((manifest_path.parent / producer["input"]).resolve())
    for finding in expected:
        if finding.get("source_artifact") == _PRODUCER_INPUT:
            finding["source_artifact"] = source
    return expected


def render_evaluation_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Engineering Review Evaluation",
        "",
        f"- Evaluation: `{result['evaluation_id']}`",
        f"- Status: **{result['status']}**",
        f"- Cases: {result['case_count']}",
        f"- Checks: {result['check_count']}",
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
        f"| Drift catalog accuracy | {metrics['drift_catalog_accuracy']:.3f} | 1.000 |",
        "",
        "## Domain coverage",
        "",
        "| Domain | Checks | Check-state accuracy |",
        "|---|---:|---:|",
    ]
    for domain in sorted(result["domain_check_counts"]):
        lines.append(
            f"| `{domain}` | {result['domain_check_counts'][domain]} | "
            f"{result['domain_check_accuracy'][domain]:.3f} |"
        )
    lines.extend([
        "",
        "## Evaluation splits",
        "",
        "| Split | Checks | Check-state accuracy |",
        "|---|---:|---:|",
    ])
    for split in sorted(result["split_check_counts"]):
        lines.append(
            f"| `{split}` | {result['split_check_counts'][split]} | "
            f"{result['split_check_accuracy'][split]:.3f} |"
        )
    lines.extend([
        "",
        "## Cases",
        "",
        "| Case | Passed | Observed status |",
        "|---|---:|---|",
    ])
    for case in result["cases"]:
        lines.append(
            f"| `{case['case_id']}` | {str(case['passed']).lower()} | {case['observed_status']} |"
        )
    if result.get("domain_drift_status_counts"):
        lines.extend([
            "",
            "## Drift catalog summary",
            "",
            "| Domain | Stable | Drifted | Not comparable |",
            "|---|---:|---:|---:|",
        ])
        for domain, counts in sorted(result["domain_drift_status_counts"].items()):
            lines.append(
                f"| `{domain}` | {counts['stable']} | {counts['drifted']} | "
                f"{counts['not-comparable']} |"
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
    drift_catalog_cases = 0
    drift_catalog_correct = 0
    drift_status_counts = {
        "stable": 0, "drifted": 0, "not-comparable": 0
    }
    domain_drift_status_counts: dict[str, dict[str, int]] = {}
    domain_check_totals: dict[str, int] = {}
    domain_check_correct: dict[str, int] = {}
    split_check_totals: dict[str, int] = {}
    split_check_correct: dict[str, int] = {}
    case_results: list[dict[str, Any]] = []

    for case in manifest["cases"]:
        case_output = output / case["case_id"]
        request_path, source_evidence = _materialize_request(
            manifest_path, manifest["schema_version"], case, case_output
        )
        runs = [
            run_review(request_path, case_output / f"run-{index + 1}")
            for index in range(repeat_runs)
        ]
        result = runs[0]
        domain = case["domain"]
        split = case["split"]
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
            domain_check_totals[domain] = domain_check_totals.get(domain, 0) + 1
            split_check_totals[split] = split_check_totals.get(split, 0) + 1
            correct = observed_status == expected_status
            check_correct += int(correct)
            domain_check_correct[domain] = domain_check_correct.get(domain, 0) + int(correct)
            split_check_correct[split] = split_check_correct.get(split, 0) + int(correct)
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
        finding_match = result["findings"] == _expected_findings(case, manifest_path)
        finding_correct += int(finding_match)
        observed_drift_catalog = [
            {key: item[key] for key in (
                "check_id", "claim_key", "baseline_artifact_id",
                "candidate_artifact_id", "status",
            )}
            for item in result.get("drift_catalog", [])
        ]
        expected_drift_catalog = case.get("expected_drift_catalog", [])
        if observed_drift_catalog:
            domain_counts = domain_drift_status_counts.setdefault(domain, {
                "stable": 0, "drifted": 0, "not-comparable": 0
            })
            for item in observed_drift_catalog:
                drift_status_counts[item["status"]] += 1
                domain_counts[item["status"]] += 1
        drift_catalog_match = observed_drift_catalog == expected_drift_catalog
        if expected_drift_catalog:
            drift_catalog_cases += 1
            drift_catalog_correct += int(drift_catalog_match)
        normalized_runs = [_normalized_result(item, excluded) for item in runs]
        repeatable = all(item == normalized_runs[0] for item in normalized_runs[1:])
        repeatable_cases += int(repeatable)

        case_passed = (
            case_status_correct
            and observed_checks == expected_checks
            and refusal_match
            and finding_match
            and drift_catalog_match
            and result["citation_validation"]["status"] == "passed"
            and (not gold_sets or any(gold <= emitted for gold in gold_sets))
            and all(item in gold_union for item in emitted)
            and repeatable
        )
        case_results.append({
            "case_id": case["case_id"],
            "domain": domain,
            "split": split,
            "passed": case_passed,
            "observed_status": result["status"],
            "observed_checks": observed_checks,
            "observed_refusal_codes": observed_refusal_codes,
            "citation_count": len(result["citations"]),
            "repeatable": repeatable,
            **(
                {"observed_drift_catalog": observed_drift_catalog}
                if observed_drift_catalog else {}
            ),
            **source_evidence,
        })

    case_count = len(manifest["cases"])
    domain_check_accuracy = {
        domain: domain_check_correct.get(domain, 0) / count
        for domain, count in sorted(domain_check_totals.items())
    }
    split_check_accuracy = {
        split: split_check_correct.get(split, 0) / count
        for split, count in sorted(split_check_totals.items())
    }
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
        "drift_catalog_accuracy": (
            drift_catalog_correct / drift_catalog_cases
            if drift_catalog_cases else 1.0
        ),
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
            "drift_catalog_accuracy",
        ))
        and metrics["false_conflict_count"] == 0
        and all(value == 1.0 for value in domain_check_accuracy.values())
        and all(value == 1.0 for value in split_check_accuracy.values())
        and all(item["passed"] for item in case_results)
    )
    timestamp = datetime.now(timezone.utc)
    evaluation = {
        "artifact_type": "engineering-review-evaluation",
        "schema_version": (
            manifest["schema_version"].replace(
                "review-evaluation-", "review-evaluation-result-"
            )
        ),
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "evaluation_id": manifest["evaluation_id"],
        "status": "passed" if gates_passed else "failed",
        "case_count": case_count,
        "check_count": check_total,
        "repeat_runs": repeat_runs,
        "domain_check_counts": dict(sorted(domain_check_totals.items())),
        "domain_check_accuracy": domain_check_accuracy,
        "split_check_counts": dict(sorted(split_check_totals.items())),
        "split_check_accuracy": split_check_accuracy,
        "drift_status_counts": (
            drift_status_counts if domain_drift_status_counts else {}
        ),
        "domain_drift_status_counts": dict(sorted(domain_drift_status_counts.items())),
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
