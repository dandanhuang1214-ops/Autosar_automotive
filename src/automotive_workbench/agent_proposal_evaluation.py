"""Freeze and score end-to-end action-proposal evaluation cohorts.

Each case uses the pinned model once to select a read-only evidence tool and pauses at
that safe boundary.  The same model then sees the verified checkpoint through the
proposal-only catalog.  Preparation and proposal behavior are scored separately so a
read-routing failure cannot be mislabeled as an action-selection failure.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_proposal import (
    ActionProposalRunner,
    verify_action_proposal,
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

MANIFEST_VERSION = "agent-proposal-evaluation-manifest-0.1"
RESULT_VERSION = "agent-proposal-evaluation-result-0.1"
MANIFEST_BOUNDARY = (
    "Cases and structural gold are frozen before target-model inference. Each case "
    "separately measures read-only checkpoint preparation and proposal-only action "
    "selection; it does not authorize or execute an action."
)
RESULT_BOUNDARY = (
    "Scoring is deterministic and artifact-based. A preparation failure remains "
    "distinct from proposal behavior, no LLM judges the result, and no action was "
    "authorized or invoked."
)
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_IMPLEMENTATION_FILES = (
    "src/automotive_workbench/agent_proposal_evaluation.py",
    "src/automotive_workbench/agent_proposal.py",
    "src/automotive_workbench/agent_runtime.py",
    "src/automotive_workbench/agent_virtual_execution.py",
    "src/automotive_workbench/model_client.py",
    "src/automotive_workbench/project_explanation.py",
)
_EXPECTED_FIELDS = {
    "proposal_status",
    "proposal_reason",
    "first_read_tool",
    "gold_facts",
    "requested_action",
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
            raise ValueError("Agent proposal evaluation bundles cannot contain symlinks")
        if path.is_file():
            files[path.relative_to(report.parent).as_posix()] = _sha256(path)
    if not files:
        raise ValueError("Agent proposal evaluation bundle is empty")
    return digest(files)


def proposal_evaluation_implementation_digest(root: Path) -> str:
    files = {
        relative: _sha256(_resolve(root, relative, "Proposal evaluation implementation"))
        for relative in _IMPLEMENTATION_FILES
    }
    return digest(files)


def _gold_facts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("gold_facts must be an array")
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


def _requested_action(value: Any, status: str) -> dict[str, Any] | None:
    if status == "declined":
        if value is not None:
            raise ValueError("Decline cases cannot expect a requested action")
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"tool_name", "arguments"}
        or not isinstance(value["tool_name"], str)
        or not value["tool_name"]
        or not isinstance(value["arguments"], dict)
    ):
        raise ValueError("Proposal cases require one exact requested action")
    canonical(value)
    return copy.deepcopy(value)


def _validate_expected(value: Any, budget: AgentBudget) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _EXPECTED_FIELDS:
        raise ValueError("Agent proposal evaluation expectation has invalid fields")
    status = value["proposal_status"]
    reason = value["proposal_reason"]
    first_tool = value["first_read_tool"]
    if status not in {"approval_required", "declined"}:
        raise ValueError("Expected proposal status is invalid")
    if not isinstance(reason, str) or not reason:
        raise ValueError("Expected proposal reason is invalid")
    if status == "approval_required" and reason != "model_proposed_typed_action":
        raise ValueError("Approval-required expectation has an invalid reason")
    if status == "declined" and not reason.startswith("model_declined:"):
        raise ValueError("Decline expectation must require a model decline")
    if not isinstance(first_tool, str) or not first_tool:
        raise ValueError("Expected first read tool is invalid")
    calls = value["max_cumulative_model_calls"]
    tokens = value["max_cumulative_total_tokens"]
    if type(calls) is not int or not 1 <= calls <= budget.max_model_calls:
        raise ValueError("Expected cumulative model calls exceed the budget")
    if type(tokens) is not int or not 1 <= tokens <= budget.max_total_tokens:
        raise ValueError("Expected cumulative tokens exceed the budget")
    return {
        "proposal_status": status,
        "proposal_reason": reason,
        "first_read_tool": first_tool,
        "gold_facts": _gold_facts(value["gold_facts"]),
        "requested_action": _requested_action(value["requested_action"], status),
        "max_cumulative_model_calls": calls,
        "max_cumulative_total_tokens": tokens,
    }


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
                "Proposal evaluation gold must identify one replayed fact: "
                + canonical(expected)
            )
        identifiers.append(matches[0])
    return identifiers


def _load_spec(path: Path, budget: AgentBudget) -> dict[str, Any]:
    spec = read(path)
    if set(spec) != {"evaluation_id", "split", "formation", "cases"}:
        raise ValueError("Agent proposal evaluation specification has invalid fields")
    if (
        not isinstance(spec["evaluation_id"], str)
        or not spec["evaluation_id"]
        or spec["split"] != "held-out"
        or not isinstance(spec["formation"], str)
        or not spec["formation"]
        or not isinstance(spec["cases"], list)
        or not spec["cases"]
    ):
        raise ValueError("Agent proposal evaluation specification metadata is invalid")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in spec["cases"]:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "category", "report", "goal", "expected"}
        ):
            raise ValueError("Agent proposal evaluation case has invalid fields")
        case_id = case["case_id"]
        if (
            not isinstance(case_id, str)
            or not _CASE_ID.fullmatch(case_id)
            or case_id in seen
            or not isinstance(case["category"], str)
            or not case["category"]
            or not isinstance(case["report"], str)
            or not case["report"]
            or not isinstance(case["goal"], str)
            or not 0 < len(case["goal"].strip()) <= 2000
        ):
            raise ValueError("Agent proposal evaluation case metadata is invalid")
        seen.add(case_id)
        cases.append(
            {
                **copy.deepcopy(case),
                "goal": case["goal"].strip(),
                "expected": _validate_expected(case["expected"], budget),
            }
        )
    return {**copy.deepcopy(spec), "cases": cases}


def freeze_agent_proposal_evaluation(
    root: Path,
    implementation_root: Path,
    spec_path: Path,
    output: Path,
    *,
    model: str,
    model_digest: str,
    budget: AgentBudget,
) -> dict[str, Any]:
    """Freeze evidence bindings and exact proposal gold before inference."""
    if output.exists() or output.is_symlink():
        raise ValueError("Agent proposal evaluation manifest output must be absent")
    if not model or not _HEX.fullmatch(model_digest):
        raise ValueError("Agent proposal evaluation model identity is invalid")
    spec = _load_spec(spec_path, budget)
    cases: list[dict[str, Any]] = []
    for case in spec["cases"]:
        report = _resolve(root, case["report"], "Agent proposal evaluation report")
        request = build_request(report, case["goal"])
        expected = copy.deepcopy(case["expected"])
        expected["gold_fact_ids"] = _gold_fact_ids(
            request, expected.pop("gold_facts")
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "report": case["report"],
                "report_sha256": request["report_sha256"],
                "bundle_sha256": _bundle_digest(report),
                "goal": case["goal"],
                "expected": expected,
            }
        )
    body = {
        "artifact_type": "agent-proposal-evaluation-manifest",
        "schema_version": MANIFEST_VERSION,
        "evaluation_id": spec["evaluation_id"],
        "split": spec["split"],
        "formation": spec["formation"],
        "spec_sha256": digest(spec),
        "implementation_sha256": proposal_evaluation_implementation_digest(
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


def load_agent_proposal_evaluation_manifest(path: Path) -> dict[str, Any]:
    manifest = read(path)
    fields = {
        "manifest_id", "artifact_type", "schema_version", "evaluation_id",
        "split", "formation", "spec_sha256", "implementation_sha256",
        "model", "budget", "cases", "boundary",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != fields
        or manifest.get("artifact_type") != "agent-proposal-evaluation-manifest"
        or manifest.get("schema_version") != MANIFEST_VERSION
        or manifest.get("split") != "held-out"
        or manifest.get("boundary") != MANIFEST_BOUNDARY
        or manifest.get("manifest_id")
        != digest({name: manifest[name] for name in manifest if name != "manifest_id"})
        or not isinstance(manifest.get("evaluation_id"), str)
        or not manifest["evaluation_id"]
        or not isinstance(manifest.get("formation"), str)
        or not manifest["formation"]
        or any(not isinstance(manifest.get(name), str) or not _HEX.fullmatch(manifest[name]) for name in ("spec_sha256", "implementation_sha256"))
        or not isinstance(manifest.get("model"), dict)
        or set(manifest["model"]) != {"name", "digest"}
        or not isinstance(manifest["model"]["name"], str)
        or not manifest["model"]["name"]
        or not isinstance(manifest["model"]["digest"], str)
        or not _HEX.fullmatch(manifest["model"]["digest"])
    ):
        raise ValueError("Invalid Agent proposal evaluation manifest metadata")
    try:
        budget = AgentBudget(**manifest["budget"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Agent proposal evaluation budget") from exc
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Agent proposal evaluation manifest requires cases")
    seen: set[str] = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "category", "report", "report_sha256", "bundle_sha256", "goal", "expected"}
            or not isinstance(case["case_id"], str)
            or not _CASE_ID.fullmatch(case["case_id"])
            or case["case_id"] in seen
            or not isinstance(case["category"], str)
            or not case["category"]
            or not isinstance(case["report"], str)
            or not case["report"]
            or not isinstance(case["goal"], str)
            or not 0 < len(case["goal"]) <= 2000
            or any(not isinstance(case[name], str) or not _HEX.fullmatch(case[name]) for name in ("report_sha256", "bundle_sha256"))
        ):
            raise ValueError("Invalid Agent proposal evaluation case metadata")
        seen.add(case["case_id"])
        expected = copy.deepcopy(case["expected"])
        if not isinstance(expected, dict) or "gold_fact_ids" not in expected:
            raise ValueError("Invalid frozen Agent proposal expectation")
        fact_ids = expected.pop("gold_fact_ids")
        expected["gold_facts"] = []
        _validate_expected(expected, budget)
        if (
            not isinstance(fact_ids, list)
            or len(set(fact_ids)) != len(fact_ids)
            or any(not isinstance(item, str) or not _HEX.fullmatch(item) for item in fact_ids)
        ):
            raise ValueError("Invalid frozen Agent proposal fact IDs")
    return manifest


def _successful_tool_events(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for event in artifact["events"]
        if event.get("kind") == "tool" and event.get("status") == "passed"
    ]


def score_agent_proposal_case(
    case: dict[str, Any],
    preparation: dict[str, Any],
    proposal: dict[str, Any] | None,
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
    status_check = selection_check = evidence_check = boundary_check = cost_check = False
    proposal_status = proposal_reason = None
    requested_action = None
    usage = copy.deepcopy(preparation["usage"])
    if is_checkpoint and proposal is not None:
        verify_action_proposal(preparation, proposal)
        proposal_status = proposal["status"]
        proposal_reason = proposal["reason"]
        requested_action = copy.deepcopy(proposal["requested_action"])
        status_check = (
            proposal_status == expected["proposal_status"]
            and proposal_reason == expected["proposal_reason"]
        )
        if expected["requested_action"] is None:
            selection_check = requested_action is None
        else:
            selection_check = (
                isinstance(requested_action, dict)
                and requested_action.get("tool_name")
                == expected["requested_action"]["tool_name"]
                and requested_action.get("arguments")
                == expected["requested_action"]["arguments"]
            )
        evidence_check = proposal["evidence_ids"] == [
            event["observation_id"] for event in tool_events
        ]
        boundary_check = (
            proposal["execution_authorized"] is False
            and proposal["tool_invoked"] is False
        )
        usage = copy.deepcopy(proposal["usage"])
        cost_check = (
            usage["cumulative_model_calls"]
            <= expected["max_cumulative_model_calls"]
            and usage["cumulative_total_tokens"]
            <= expected["max_cumulative_total_tokens"]
        )
    checks = {
        "checkpoint_preparation": preparation_check,
        "proposal_status": status_check,
        "action_selection": selection_check,
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
        "proposal_status": proposal_status,
        "proposal_reason": proposal_reason,
        "requested_action": requested_action,
        "checks": checks,
        "usage": usage,
    }


def _result_body(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    check_names = (
        "checkpoint_preparation", "proposal_status", "action_selection",
        "evidence_binding", "non_execution_boundary", "cost",
    )
    totals = {name: sum(row["checks"][name] for row in rows) for name in check_names}
    body = {
        "artifact_type": "agent-proposal-evaluation-result",
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


def run_agent_proposal_evaluation(
    root: Path,
    implementation_root: Path,
    manifest_path: Path,
    expected_manifest_id: str,
    output: Path,
    *,
    client: ModelClient,
) -> dict[str, Any]:
    manifest = load_agent_proposal_evaluation_manifest(manifest_path)
    if manifest["manifest_id"] != expected_manifest_id:
        raise ValueError("Agent proposal manifest ID differs from the frozen ID")
    if manifest["implementation_sha256"] != proposal_evaluation_implementation_digest(implementation_root):
        raise ValueError("Agent proposal evaluation implementation differs from frozen code")
    if output.exists() or output.is_symlink():
        raise ValueError("Agent proposal evaluation output must be absent")
    reports: dict[str, Path] = {}
    for case in manifest["cases"]:
        report = _resolve(root, case["report"], "Agent proposal evaluation report")
        request = build_request(report, case["goal"])
        if request["report_sha256"] != case["report_sha256"] or _bundle_digest(report) != case["bundle_sha256"]:
            raise ValueError("Frozen Agent proposal evidence changed: " + case["case_id"])
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
            raise ValueError("Agent proposal evaluation model differs from frozen identity")
        preparation_name = f"{case['case_id']}-preparation.json"
        (artifacts / preparation_name).write_text(
            canonical(preparation) + "\n", encoding="utf-8", newline="\n"
        )
        proposal = None
        proposal_name = None
        if preparation.get("schema_version") == "readonly-agent-checkpoint-0.1":
            proposal = ActionProposalRunner(client).run(preparation)
            proposal_name = f"{case['case_id']}-proposal.json"
            (artifacts / proposal_name).write_text(
                canonical(proposal) + "\n", encoding="utf-8", newline="\n"
            )
        row = score_agent_proposal_case(case, preparation, proposal)
        row["preparation_artifact"] = f"artifacts/{preparation_name}"
        row["proposal_artifact"] = (
            f"artifacts/{proposal_name}" if proposal_name is not None else None
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


def verify_agent_proposal_evaluation(
    manifest_path: Path, directory: Path
) -> dict[str, Any]:
    manifest = load_agent_proposal_evaluation_manifest(manifest_path)
    result = read(directory / "evaluation.json")
    fields = {
        "result_id", "artifact_type", "schema_version", "status",
        "evaluation_id", "manifest_id", "split", "model", "semantic_status",
        "summary", "cases", "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result.get("artifact_type") != "agent-proposal-evaluation-result"
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
        raise ValueError("Invalid Agent proposal evaluation result metadata")
    rows: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        if not isinstance(recorded, dict) or recorded.get("case_id") != case["case_id"]:
            raise ValueError("Agent proposal evaluation result case order differs")
        preparation_relative = recorded.get("preparation_artifact")
        proposal_relative = recorded.get("proposal_artifact")
        if not isinstance(preparation_relative, str) or (
            proposal_relative is not None and not isinstance(proposal_relative, str)
        ):
            raise ValueError("Agent proposal evaluation artifact path is invalid")
        preparation = read(_resolve(directory, preparation_relative, "Preparation artifact"))
        proposal = (
            read(_resolve(directory, proposal_relative, "Proposal artifact"))
            if proposal_relative is not None
            else None
        )
        row = score_agent_proposal_case(case, preparation, proposal)
        row["preparation_artifact"] = preparation_relative
        row["proposal_artifact"] = proposal_relative
        if canonical(row) != canonical(recorded):
            raise ValueError("Agent proposal evaluation result differs from artifact scoring")
        rows.append(row)
    expected = _result_body(manifest, rows)
    if canonical(expected) != canonical(result):
        raise ValueError("Agent proposal evaluation summary differs from artifacts")
    return {
        "status": "passed",
        "evaluation_status": result["status"],
        "result_id": result["result_id"],
        "manifest_id": manifest["manifest_id"],
        "case_count": len(rows),
    }
