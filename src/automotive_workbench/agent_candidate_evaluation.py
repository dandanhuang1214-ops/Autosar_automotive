"""Freeze and score read-then-select action-candidate cohorts.

The control plane freezes exact candidate templates before target-model inference.
After a case reaches a verified read-only checkpoint, those templates are sealed to
the checkpoint and the model can only select a candidate ID or decline.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_action_candidate import (
    CandidateSelectionRunner,
    issue_action_candidate,
    verify_action_candidate,
    verify_candidate_selection,
)
from automotive_workbench.agent_proposal import (
    ActionCatalog,
    build_restricted_action_catalog,
)
from automotive_workbench.agent_runtime import (
    AgentBudget,
    AgentRunner,
    build_readonly_registry,
    verify_agent_checkpoint,
    verify_agent_trace,
)
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import (
    build_request,
    canonical,
    digest,
    read,
)


MANIFEST_VERSION = "agent-candidate-evaluation-manifest-0.1"
RESULT_VERSION = "agent-candidate-evaluation-result-0.1"
MANIFEST_BOUNDARY = (
    "Cases, structural gold, and exact action templates are frozen before "
    "target-model inference. Runtime candidate IDs bind the resulting read-only "
    "checkpoint; selection does not authorize or execute an action."
)
RESULT_BOUNDARY = (
    "Scoring is deterministic and artifact-based. Checkpoint preparation, "
    "control-plane candidate issuance, and ID-only model selection are measured "
    "separately; no LLM judges the result and no action was authorized or invoked."
)
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_IMPLEMENTATION_FILES = (
    "scripts/run_agent_candidate_evaluation.py",
    "schemas/agent-action-candidate.schema.json",
    "schemas/agent-action-candidate-selection.schema.json",
    "schemas/agent-candidate-evaluation-manifest.schema.json",
    "schemas/agent-candidate-evaluation-result.schema.json",
    "src/automotive_workbench/agent_candidate_evaluation.py",
    "src/automotive_workbench/agent_action_candidate.py",
    "src/automotive_workbench/agent_runtime.py",
    "src/automotive_workbench/model_client.py",
    "src/automotive_workbench/project_explanation.py",
)
_EXPECTED_FIELDS = {
    "selection_status",
    "selection_reason",
    "selected_candidate_key",
    "first_read_tool",
    "gold_facts",
    "max_cumulative_model_calls",
    "max_cumulative_total_tokens",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label} must be a contained relative path")
    path = root / candidate
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} does not identify a regular file")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"{label} escapes the evaluation root")
    return path


def _bundle_digest(report: Path) -> str:
    files: dict[str, str] = {}
    for path in sorted(report.parent.rglob("*")):
        if path.is_symlink():
            raise ValueError("Agent candidate evaluation bundles cannot contain symlinks")
        if path.is_file():
            files[path.relative_to(report.parent).as_posix()] = _sha256(path)
    if not files:
        raise ValueError("Agent candidate evaluation bundle is empty")
    return digest(files)


def candidate_evaluation_implementation_digest(root: Path) -> str:
    files = {
        relative: _sha256(_resolve(root, relative, "Candidate evaluation implementation"))
        for relative in _IMPLEMENTATION_FILES
    }
    return digest(files)


def _gold_facts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("gold_facts must be a non-empty array")
    result: list[dict[str, Any]] = []
    for fact in value:
        if (
            not isinstance(fact, dict)
            or set(fact) != {"artifact_id", "pointer", "value"}
            or not isinstance(fact["artifact_id"], str)
            or not fact["artifact_id"]
            or not isinstance(fact["pointer"], str)
            or not fact["pointer"].startswith("/")
        ):
            raise ValueError("gold_facts contains an invalid structural fact")
        canonical(fact["value"])
        result.append(copy.deepcopy(fact))
    if len({canonical(item) for item in result}) != len(result):
        raise ValueError("gold_facts contains duplicates")
    return result


def _gold_fact_ids(request: dict[str, Any], gold: list[dict[str, Any]]) -> list[str]:
    identifiers: list[str] = []
    for expected in gold:
        matches = [
            fact["fact_id"]
            for fact in request["facts"]
            if all(canonical(fact[name]) == canonical(item) for name, item in expected.items())
        ]
        if len(matches) != 1:
            raise ValueError(
                "Candidate evaluation gold must identify one replayed fact: "
                + canonical(expected)
            )
        identifiers.append(matches[0])
    return identifiers


def _action_template(
    catalog: ActionCatalog, tool_name: Any, arguments: Any
) -> dict[str, Any]:
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("Candidate template tool_name is invalid")
    checked = catalog.validate(tool_name, arguments)
    body = {
        "tool_name": tool_name,
        "permission": catalog.permission(tool_name),
        "arguments": checked,
    }
    return {**body, "call_id": digest(body)}


def _validate_expected(
    value: Any, budget: AgentBudget, candidate_keys: set[str]
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _EXPECTED_FIELDS:
        raise ValueError("Agent candidate evaluation expectation has invalid fields")
    status = value["selection_status"]
    reason = value["selection_reason"]
    selected_key = value["selected_candidate_key"]
    if status not in {"approval_required", "declined"}:
        raise ValueError("Expected candidate selection status is invalid")
    if not isinstance(reason, str) or not reason:
        raise ValueError("Expected candidate selection reason is invalid")
    if status == "approval_required":
        if reason != "model_selected_control_plane_candidate":
            raise ValueError("Selected candidate expectation has an invalid reason")
        if not isinstance(selected_key, str) or selected_key not in candidate_keys:
            raise ValueError("Expected selected candidate key is not declared")
    elif (
        not reason.startswith("model_declined:")
        or selected_key is not None
    ):
        raise ValueError("Decline expectation is invalid")
    first_tool = value["first_read_tool"]
    calls = value["max_cumulative_model_calls"]
    tokens = value["max_cumulative_total_tokens"]
    if not isinstance(first_tool, str) or not first_tool:
        raise ValueError("Expected first read tool is invalid")
    if type(calls) is not int or not 1 <= calls <= budget.max_model_calls:
        raise ValueError("Expected cumulative model calls exceed the budget")
    if type(tokens) is not int or not 1 <= tokens <= budget.max_total_tokens:
        raise ValueError("Expected cumulative tokens exceed the budget")
    return {
        "selection_status": status,
        "selection_reason": reason,
        "selected_candidate_key": selected_key,
        "first_read_tool": first_tool,
        "gold_facts": _gold_facts(value["gold_facts"]),
        "max_cumulative_model_calls": calls,
        "max_cumulative_total_tokens": tokens,
    }


def _load_spec(
    path: Path, budget: AgentBudget, catalog: ActionCatalog
) -> dict[str, Any]:
    spec = read(path)
    if set(spec) != {"evaluation_id", "split", "formation", "cases"}:
        raise ValueError("Agent candidate evaluation specification has invalid fields")
    if (
        not isinstance(spec["evaluation_id"], str)
        or not spec["evaluation_id"]
        or spec["split"] != "held-out"
        or not isinstance(spec["formation"], str)
        or not spec["formation"]
        or not isinstance(spec["cases"], list)
        or not spec["cases"]
    ):
        raise ValueError("Agent candidate evaluation specification metadata is invalid")
    cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for case in spec["cases"]:
        if (
            not isinstance(case, dict)
            or set(case)
            != {"case_id", "category", "report", "goal", "candidates", "expected"}
        ):
            raise ValueError("Agent candidate evaluation case has invalid fields")
        case_id = case["case_id"]
        if (
            not isinstance(case_id, str)
            or not _CASE_ID.fullmatch(case_id)
            or case_id in seen_cases
            or not isinstance(case["category"], str)
            or not case["category"]
            or not isinstance(case["report"], str)
            or not case["report"]
            or not isinstance(case["goal"], str)
            or not 0 < len(case["goal"].strip()) <= 2000
            or not isinstance(case["candidates"], list)
            or not case["candidates"]
        ):
            raise ValueError("Agent candidate evaluation case metadata is invalid")
        seen_cases.add(case_id)
        candidates: list[dict[str, Any]] = []
        keys: set[str] = set()
        for item in case["candidates"]:
            if (
                not isinstance(item, dict)
                or set(item)
                != {"candidate_key", "tool_name", "arguments", "evidence_gold_facts"}
                or not isinstance(item["candidate_key"], str)
                or not _CASE_ID.fullmatch(item["candidate_key"])
                or item["candidate_key"] in keys
            ):
                raise ValueError("Agent candidate template is invalid")
            keys.add(item["candidate_key"])
            candidates.append(
                {
                    "candidate_key": item["candidate_key"],
                    "action": _action_template(
                        catalog, item["tool_name"], item["arguments"]
                    ),
                    "evidence_gold_facts": _gold_facts(
                        item["evidence_gold_facts"]
                    ),
                }
            )
        cases.append(
            {
                "case_id": case_id,
                "category": case["category"],
                "report": case["report"],
                "goal": case["goal"].strip(),
                "candidates": candidates,
                "expected": _validate_expected(case["expected"], budget, keys),
            }
        )
    return {**copy.deepcopy(spec), "cases": cases}


def freeze_agent_candidate_evaluation(
    root: Path,
    implementation_root: Path,
    spec_path: Path,
    output: Path,
    *,
    model: str,
    model_digest: str,
    budget: AgentBudget,
) -> dict[str, Any]:
    """Freeze evidence, action templates, structural gold, and model identity."""
    if output.exists() or output.is_symlink():
        raise ValueError("Agent candidate evaluation manifest output must be absent")
    if not model or not _HEX.fullmatch(model_digest):
        raise ValueError("Agent candidate evaluation model identity is invalid")
    catalog = build_restricted_action_catalog()
    spec = _load_spec(spec_path, budget, catalog)
    cases: list[dict[str, Any]] = []
    for case in spec["cases"]:
        report = _resolve(root, case["report"], "Agent candidate evaluation report")
        request = build_request(report, case["goal"])
        expected = copy.deepcopy(case["expected"])
        expected["gold_fact_ids"] = _gold_fact_ids(
            request, expected.pop("gold_facts")
        )
        candidates = []
        for item in case["candidates"]:
            candidates.append(
                {
                    "candidate_key": item["candidate_key"],
                    "action": copy.deepcopy(item["action"]),
                    "evidence_fact_ids": _gold_fact_ids(
                        request, item["evidence_gold_facts"]
                    ),
                }
            )
        cases.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "report": case["report"],
                "report_sha256": request["report_sha256"],
                "bundle_sha256": _bundle_digest(report),
                "goal": case["goal"],
                "candidates": candidates,
                "expected": expected,
            }
        )
    body = {
        "artifact_type": "agent-candidate-evaluation-manifest",
        "schema_version": MANIFEST_VERSION,
        "evaluation_id": spec["evaluation_id"],
        "split": spec["split"],
        "formation": spec["formation"],
        "spec_sha256": digest(read(spec_path)),
        "implementation_sha256": candidate_evaluation_implementation_digest(
            implementation_root
        ),
        "model": {"name": model, "digest": model_digest},
        "budget": budget.as_dict(),
        "cases": cases,
        "boundary": MANIFEST_BOUNDARY,
    }
    manifest = {"manifest_id": digest(body), **body}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


def load_agent_candidate_evaluation_manifest(path: Path) -> dict[str, Any]:
    manifest = read(path)
    fields = {
        "manifest_id", "artifact_type", "schema_version", "evaluation_id",
        "split", "formation", "spec_sha256", "implementation_sha256",
        "model", "budget", "cases", "boundary",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != fields
        or manifest.get("artifact_type") != "agent-candidate-evaluation-manifest"
        or manifest.get("schema_version") != MANIFEST_VERSION
        or manifest.get("split") != "held-out"
        or manifest.get("boundary") != MANIFEST_BOUNDARY
        or manifest.get("manifest_id")
        != digest({name: manifest[name] for name in manifest if name != "manifest_id"})
        or not isinstance(manifest.get("evaluation_id"), str)
        or not manifest["evaluation_id"]
        or not isinstance(manifest.get("formation"), str)
        or not manifest["formation"]
        or any(
            not isinstance(manifest.get(name), str) or not _HEX.fullmatch(manifest[name])
            for name in ("spec_sha256", "implementation_sha256")
        )
        or not isinstance(manifest.get("model"), dict)
        or set(manifest["model"]) != {"name", "digest"}
        or not isinstance(manifest["model"]["name"], str)
        or not manifest["model"]["name"]
        or not isinstance(manifest["model"]["digest"], str)
        or not _HEX.fullmatch(manifest["model"]["digest"])
    ):
        raise ValueError("Invalid Agent candidate evaluation manifest metadata")
    try:
        budget = AgentBudget(**manifest["budget"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Agent candidate evaluation budget") from exc
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Agent candidate evaluation manifest requires cases")
    catalog = build_restricted_action_catalog()
    seen: set[str] = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case)
            != {
                "case_id", "category", "report", "report_sha256",
                "bundle_sha256", "goal", "candidates", "expected",
            }
            or not isinstance(case["case_id"], str)
            or not _CASE_ID.fullmatch(case["case_id"])
            or case["case_id"] in seen
            or not isinstance(case["category"], str)
            or not case["category"]
            or not isinstance(case["report"], str)
            or not case["report"]
            or not isinstance(case["goal"], str)
            or not 0 < len(case["goal"]) <= 2000
            or any(
                not isinstance(case[name], str) or not _HEX.fullmatch(case[name])
                for name in ("report_sha256", "bundle_sha256")
            )
        ):
            raise ValueError("Invalid Agent candidate evaluation case metadata")
        seen.add(case["case_id"])
        candidates = case.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Invalid frozen Agent candidate templates")
        keys: set[str] = set()
        for item in candidates:
            if (
                not isinstance(item, dict)
                or set(item) != {"candidate_key", "action", "evidence_fact_ids"}
                or not isinstance(item["candidate_key"], str)
                or not _CASE_ID.fullmatch(item["candidate_key"])
                or item["candidate_key"] in keys
                or not isinstance(item["action"], dict)
                or set(item["action"])
                != {"tool_name", "permission", "arguments", "call_id"}
                or not isinstance(item["evidence_fact_ids"], list)
                or not item["evidence_fact_ids"]
                or len(set(item["evidence_fact_ids"]))
                != len(item["evidence_fact_ids"])
                or any(
                    not isinstance(fact_id, str) or not _HEX.fullmatch(fact_id)
                    for fact_id in item["evidence_fact_ids"]
                )
            ):
                raise ValueError("Invalid frozen Agent candidate template")
            if item["action"] != _action_template(
                catalog,
                item["action"].get("tool_name"),
                item["action"].get("arguments"),
            ):
                raise ValueError("Invalid frozen Agent candidate template")
            keys.add(item["candidate_key"])
        expected = copy.deepcopy(case.get("expected"))
        if not isinstance(expected, dict) or "gold_fact_ids" not in expected:
            raise ValueError("Invalid frozen Agent candidate expectation")
        fact_ids = expected.pop("gold_fact_ids")
        expected["gold_facts"] = [
            {"artifact_id": "frozen", "pointer": "/frozen", "value": item}
            for item in fact_ids
        ]
        _validate_expected(expected, budget, keys)
        if (
            not isinstance(fact_ids, list)
            or not fact_ids
            or len(set(fact_ids)) != len(fact_ids)
            or any(not isinstance(item, str) or not _HEX.fullmatch(item) for item in fact_ids)
        ):
            raise ValueError("Invalid frozen Agent candidate fact IDs")
    return manifest


def _successful_tool_events(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for event in artifact["events"]
        if event.get("kind") == "tool" and event.get("status") == "passed"
    ]


def _candidate_evidence_ids(
    checkpoint: dict[str, Any], fact_ids: list[str]
) -> list[str] | None:
    required = set(fact_ids)
    covered: set[str] = set()
    observations: list[str] = []
    for event in _successful_tool_events(checkpoint):
        event_facts = {
            fact["fact_id"]
            for fact in event.get("result", {}).get("facts", [])
            if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str)
        }
        if required & event_facts:
            observations.append(event["observation_id"])
            covered.update(required & event_facts)
    return observations if covered == required and observations else None


def _issue_case_candidates(
    checkpoint: dict[str, Any], case: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    issued: list[tuple[str, dict[str, Any]]] = []
    for template in case["candidates"]:
        evidence_ids = _candidate_evidence_ids(
            checkpoint, template["evidence_fact_ids"]
        )
        if evidence_ids is None:
            return []
        action = template["action"]
        candidate = issue_action_candidate(
            checkpoint,
            tool_name=action["tool_name"],
            arguments=action["arguments"],
            evidence_ids=evidence_ids,
        )
        issued.append((template["candidate_key"], candidate))
    return issued


def score_agent_candidate_case(
    case: dict[str, Any],
    preparation: dict[str, Any],
    candidates: list[tuple[str, dict[str, Any]]],
    selection: dict[str, Any] | None,
) -> dict[str, Any]:
    expected = case["expected"]
    is_checkpoint = preparation.get("schema_version") == "readonly-agent-checkpoint-0.1"
    if is_checkpoint:
        verify_agent_checkpoint(preparation)
    else:
        verify_agent_trace(preparation)
    tool_events = _successful_tool_events(preparation)
    first_tool = tool_events[0]["tool_name"] if tool_events else None
    selected_facts = {
        fact["fact_id"]
        for event in tool_events
        for fact in event.get("result", {}).get("facts", [])
        if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str)
    }
    gold = set(expected["gold_fact_ids"])
    preparation_check = (
        is_checkpoint
        and first_tool == expected["first_read_tool"]
        and gold <= selected_facts
    )
    candidate_check = False
    if is_checkpoint and len(candidates) == len(case["candidates"]):
        candidate_check = True
        for template, (key, candidate) in zip(
            case["candidates"], candidates, strict=True
        ):
            verify_action_candidate(preparation, candidate)
            candidate_evidence = _candidate_evidence_ids(
                preparation, template["evidence_fact_ids"]
            )
            if (
                key != template["candidate_key"]
                or candidate["action"] != template["action"]
                or candidate["evidence_ids"] != candidate_evidence
            ):
                candidate_check = False
    status_check = selection_check = evidence_check = boundary_check = cost_check = False
    selection_status = selection_reason = selected_key = None
    requested_action = None
    usage = copy.deepcopy(preparation["usage"])
    if is_checkpoint and candidate_check and selection is not None:
        candidate_values = [item for _, item in candidates]
        verify_candidate_selection(preparation, candidate_values, selection)
        selection_status = selection["status"]
        selection_reason = selection["reason"]
        requested_action = copy.deepcopy(selection["requested_action"])
        by_id = {item["candidate_id"]: key for key, item in candidates}
        selected_key = by_id.get(selection["selected_candidate_id"])
        status_check = (
            selection_status == expected["selection_status"]
            and selection_reason == expected["selection_reason"]
        )
        selection_check = selected_key == expected["selected_candidate_key"]
        if expected["selected_candidate_key"] is None:
            selection_check = selection_check and requested_action is None
        else:
            expected_action = next(
                item["action"]
                for item in case["candidates"]
                if item["candidate_key"] == expected["selected_candidate_key"]
            )
            selection_check = selection_check and requested_action == expected_action
        combined_evidence: list[str] = []
        for _, candidate in sorted(candidates, key=lambda pair: pair[1]["candidate_id"]):
            for evidence_id in candidate["evidence_ids"]:
                if evidence_id not in combined_evidence:
                    combined_evidence.append(evidence_id)
        evidence_check = selection["evidence_ids"] == combined_evidence
        boundary_check = (
            selection["execution_authorized"] is False
            and selection["tool_invoked"] is False
            and all(
                candidate["execution_authorized"] is False
                and candidate["tool_invoked"] is False
                for _, candidate in candidates
            )
        )
        usage = copy.deepcopy(selection["usage"])
        cost_check = (
            usage["cumulative_model_calls"]
            <= expected["max_cumulative_model_calls"]
            and usage["cumulative_total_tokens"]
            <= expected["max_cumulative_total_tokens"]
        )
    checks = {
        "checkpoint_preparation": preparation_check,
        "candidate_issuance": candidate_check,
        "selection_status": status_check,
        "candidate_selection": selection_check,
        "evidence_binding": evidence_check,
        "non_execution_boundary": boundary_check,
        "cost": cost_check,
    }
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "status": "passed" if all(checks.values()) else "failed",
        "preparation_kind": "checkpoint" if is_checkpoint else "trace",
        "preparation_status": preparation["status"],
        "preparation_reason": preparation["reason"],
        "first_read_tool": first_tool,
        "selected_gold_facts": len(gold & selected_facts),
        "required_gold_facts": len(gold),
        "issued_candidates": [
            {
                "candidate_key": key,
                "candidate_id": candidate["candidate_id"],
                "action": copy.deepcopy(candidate["action"]),
            }
            for key, candidate in candidates
        ],
        "selection_status": selection_status,
        "selection_reason": selection_reason,
        "selected_candidate_key": selected_key,
        "requested_action": requested_action,
        "checks": checks,
        "usage": usage,
    }


def _result_body(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    check_names = (
        "checkpoint_preparation", "candidate_issuance", "selection_status",
        "candidate_selection", "evidence_binding", "non_execution_boundary", "cost",
    )
    totals = {name: sum(row["checks"][name] for row in rows) for name in check_names}
    body = {
        "artifact_type": "agent-candidate-evaluation-result",
        "schema_version": RESULT_VERSION,
        "status": "passed" if all(row["status"] == "passed" for row in rows) else "failed",
        "evaluation_id": manifest["evaluation_id"],
        "manifest_id": manifest["manifest_id"],
        "split": manifest["split"],
        "model": copy.deepcopy(manifest["model"]),
        "semantic_status": "unassessed",
        "summary": {
            "case_count": len(rows),
            "passed_cases": sum(row["status"] == "passed" for row in rows),
            "failed_cases": sum(row["status"] == "failed" for row in rows),
            "check_pass_counts": totals,
            "cumulative_total_tokens": sum(
                row["usage"].get("cumulative_total_tokens", row["usage"]["total_tokens"])
                for row in rows
            ),
        },
        "cases": rows,
        "boundary": RESULT_BOUNDARY,
    }
    return {"result_id": digest(body), **body}


def run_agent_candidate_evaluation(
    root: Path,
    implementation_root: Path,
    manifest_path: Path,
    expected_manifest_id: str,
    output: Path,
    *,
    client: ModelClient,
) -> dict[str, Any]:
    manifest = load_agent_candidate_evaluation_manifest(manifest_path)
    if manifest["manifest_id"] != expected_manifest_id:
        raise ValueError("Agent candidate manifest ID differs from the frozen ID")
    if manifest["implementation_sha256"] != candidate_evaluation_implementation_digest(
        implementation_root
    ):
        raise ValueError("Agent candidate evaluation implementation differs from frozen code")
    if output.exists() or output.is_symlink():
        raise ValueError("Agent candidate evaluation output must be absent")
    reports: dict[str, Path] = {}
    for case in manifest["cases"]:
        report = _resolve(root, case["report"], "Agent candidate evaluation report")
        request = build_request(report, case["goal"])
        if (
            request["report_sha256"] != case["report_sha256"]
            or _bundle_digest(report) != case["bundle_sha256"]
        ):
            raise ValueError("Frozen Agent candidate evidence changed: " + case["case_id"])
        reports[case["case_id"]] = report
    output.mkdir(parents=True)
    artifacts = output / "artifacts"
    artifacts.mkdir()
    budget = AgentBudget(**manifest["budget"])
    rows: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        preparation = AgentRunner(
            client, build_readonly_registry(reports[case["case_id"]]), budget
        ).run(case["goal"], manifest["model"]["name"], pause_after_tool_calls=1)
        preparation_model = preparation.get("model")
        if preparation_model is not None and (
            preparation_model.get("name") != manifest["model"]["name"]
            or preparation_model.get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Agent candidate evaluation model differs from frozen identity")
        preparation_name = f"{case['case_id']}-preparation.json"
        (artifacts / preparation_name).write_text(
            canonical(preparation) + "\n", encoding="utf-8", newline="\n"
        )
        candidates: list[tuple[str, dict[str, Any]]] = []
        selection = None
        selection_name = None
        candidate_paths: list[dict[str, str]] = []
        if preparation.get("schema_version") == "readonly-agent-checkpoint-0.1":
            candidates = _issue_case_candidates(preparation, case)
            for key, candidate in candidates:
                candidate_name = f"{case['case_id']}-candidate-{key}.json"
                (artifacts / candidate_name).write_text(
                    canonical(candidate) + "\n", encoding="utf-8", newline="\n"
                )
                candidate_paths.append(
                    {"candidate_key": key, "artifact": f"artifacts/{candidate_name}"}
                )
            if candidates:
                selection = CandidateSelectionRunner(client).run(
                    preparation, [item for _, item in candidates]
                )
                selection_name = f"{case['case_id']}-selection.json"
                (artifacts / selection_name).write_text(
                    canonical(selection) + "\n", encoding="utf-8", newline="\n"
                )
        row = score_agent_candidate_case(case, preparation, candidates, selection)
        row["preparation_artifact"] = f"artifacts/{preparation_name}"
        row["candidate_artifacts"] = candidate_paths
        row["selection_artifact"] = (
            f"artifacts/{selection_name}" if selection_name is not None else None
        )
        rows.append(row)
        (output / "partial.json").write_text(
            canonical(
                {
                    "complete": False,
                    "evaluation_id": manifest["evaluation_id"],
                    "manifest_id": manifest["manifest_id"],
                    "cases": rows,
                }
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    result = _result_body(manifest, rows)
    (output / "evaluation.json").write_text(
        canonical(result) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def verify_agent_candidate_evaluation(
    manifest_path: Path, directory: Path
) -> dict[str, Any]:
    manifest = load_agent_candidate_evaluation_manifest(manifest_path)
    result = read(directory / "evaluation.json")
    fields = {
        "result_id", "artifact_type", "schema_version", "status",
        "evaluation_id", "manifest_id", "split", "model", "semantic_status",
        "summary", "cases", "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result.get("artifact_type") != "agent-candidate-evaluation-result"
        or result.get("schema_version") != RESULT_VERSION
        or result.get("boundary") != RESULT_BOUNDARY
        or result.get("semantic_status") != "unassessed"
        or result.get("evaluation_id") != manifest["evaluation_id"]
        or result.get("manifest_id") != manifest["manifest_id"]
        or result.get("split") != manifest["split"]
        or result.get("model") != manifest["model"]
        or result.get("result_id")
        != digest({name: result[name] for name in result if name != "result_id"})
        or not isinstance(result.get("cases"), list)
        or len(result["cases"]) != len(manifest["cases"])
    ):
        raise ValueError("Invalid Agent candidate evaluation result metadata")
    rows: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        if not isinstance(recorded, dict) or recorded.get("case_id") != case["case_id"]:
            raise ValueError("Agent candidate evaluation result case order differs")
        preparation_relative = recorded.get("preparation_artifact")
        candidate_artifacts = recorded.get("candidate_artifacts")
        selection_relative = recorded.get("selection_artifact")
        if (
            not isinstance(preparation_relative, str)
            or not isinstance(candidate_artifacts, list)
            or (
                selection_relative is not None
                and not isinstance(selection_relative, str)
            )
        ):
            raise ValueError("Agent candidate evaluation artifact path is invalid")
        preparation = read(
            _resolve(directory, preparation_relative, "Preparation artifact")
        )
        candidates: list[tuple[str, dict[str, Any]]] = []
        for item in candidate_artifacts:
            if (
                not isinstance(item, dict)
                or set(item) != {"candidate_key", "artifact"}
                or not isinstance(item["candidate_key"], str)
                or not isinstance(item["artifact"], str)
            ):
                raise ValueError("Agent candidate evaluation artifact path is invalid")
            candidates.append(
                (
                    item["candidate_key"],
                    read(_resolve(directory, item["artifact"], "Candidate artifact")),
                )
            )
        selection = (
            read(_resolve(directory, selection_relative, "Selection artifact"))
            if selection_relative is not None
            else None
        )
        row = score_agent_candidate_case(case, preparation, candidates, selection)
        row["preparation_artifact"] = preparation_relative
        row["candidate_artifacts"] = candidate_artifacts
        row["selection_artifact"] = selection_relative
        if canonical(row) != canonical(recorded):
            raise ValueError("Agent candidate evaluation result differs from artifact scoring")
        rows.append(row)
    expected = _result_body(manifest, rows)
    if canonical(expected) != canonical(result):
        raise ValueError("Agent candidate evaluation summary differs from artifacts")
    return {
        "status": "passed",
        "evaluation_status": result["status"],
        "result_id": result["result_id"],
        "manifest_id": manifest["manifest_id"],
        "case_count": len(rows),
    }
