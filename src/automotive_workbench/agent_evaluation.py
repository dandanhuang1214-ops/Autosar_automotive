"""Freeze and score held-out read-only Agent traces without an LLM judge."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_runtime import (
    AgentBudget,
    AgentRunner,
    build_readonly_registry,
    save_agent_trace,
    verify_agent_trace,
)
from automotive_workbench.explanation_services import ServiceEndpoint
from automotive_workbench.knowledge_policy import (
    load_agent_knowledge_policy,
    validate_agent_knowledge_policy,
)
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import (
    build_request,
    canonical,
    digest,
    read,
)

MANIFEST_VERSION = "readonly-agent-evaluation-manifest-0.1"
RESULT_VERSION = "readonly-agent-evaluation-result-0.1"
MANIFEST_BOUNDARY = (
    "Questions and structural gold are frozen before inference. This cohort measures "
    "tool choice, effective parameters, evidence citation, policy refusal, and cost; "
    "it does not certify prose semantics or human usability."
)
RESULT_BOUNDARY = (
    "Scoring is deterministic and trace-based. Runtime guard refusal is distinct from "
    "a model-declared policy refusal, and model prose remains unassessed."
)
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_IMPLEMENTATION_FILES = (
    "src/automotive_workbench/agent_evaluation.py",
    "src/automotive_workbench/agent_runtime.py",
    "src/automotive_workbench/explanation_services.py",
    "src/automotive_workbench/knowledge_policy.py",
    "src/automotive_workbench/model_client.py",
    "src/automotive_workbench/model_explanation.py",
    "src/automotive_workbench/project_ecuc.py",
    "src/automotive_workbench/project_explanation.py",
)
_EXPECTED_FIELDS = {
    "status",
    "reason_prefix",
    "first_tool",
    "required_tools",
    "forbidden_tools",
    "required_evidence_tools",
    "gold_facts",
    "knowledge_document_ids",
    "max_model_calls",
    "max_tool_calls",
    "max_total_tokens",
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
            raise ValueError("Agent evaluation bundles cannot contain symlinks")
        if path.is_file():
            relative = path.relative_to(report.parent).as_posix()
            files[relative] = _sha256(path)
    if not files:
        raise ValueError("Agent evaluation report bundle is empty")
    return digest(files)


def implementation_digest(root: Path) -> str:
    files: dict[str, str] = {}
    for relative in _IMPLEMENTATION_FILES:
        path = _resolve(root, relative, "Agent evaluation implementation")
        files[relative] = _sha256(path)
    return digest(files)


def _string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or len(set(value)) != len(value)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ValueError(f"{label} must be a unique string array")
    return copy.deepcopy(value)


def _gold_facts(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    facts: list[dict[str, Any]] = []
    for fact in value:
        if (
            not isinstance(fact, dict)
            or set(fact) != {"artifact_id", "pointer", "value"}
            or not isinstance(fact["artifact_id"], str)
            or not fact["artifact_id"]
            or not isinstance(fact["pointer"], str)
            or not fact["pointer"].startswith("/")
        ):
            raise ValueError(f"{label} contains an invalid structural fact")
        canonical(fact["value"])
        facts.append(copy.deepcopy(fact))
    if len({canonical(fact) for fact in facts}) != len(facts):
        raise ValueError(f"{label} contains duplicate structural facts")
    return facts


def _validate_expected(value: Any, budget: AgentBudget) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _EXPECTED_FIELDS:
        raise ValueError("Agent evaluation expectation has invalid fields")
    status = value["status"]
    reason_prefix = value["reason_prefix"]
    first_tool = value["first_tool"]
    if status not in {"passed", "refused"}:
        raise ValueError("Agent evaluation expected status is invalid")
    if not isinstance(reason_prefix, str) or not reason_prefix:
        raise ValueError("Agent evaluation reason prefix is invalid")
    if first_tool is not None and (
        not isinstance(first_tool, str) or not first_tool
    ):
        raise ValueError("Agent evaluation first tool is invalid")
    required = _string_list(value["required_tools"], "required_tools")
    forbidden = _string_list(value["forbidden_tools"], "forbidden_tools")
    evidence = _string_list(
        value["required_evidence_tools"], "required_evidence_tools"
    )
    if set(required) & set(forbidden):
        raise ValueError("Required and forbidden Agent tools overlap")
    if first_tool is not None and first_tool not in required:
        raise ValueError("First Agent tool must also be required")
    if not set(evidence) <= set(required):
        raise ValueError("Evidence tools must be required tools")
    if status == "refused" and (required or evidence or first_tool is not None):
        raise ValueError("Policy-refusal cases cannot require a tool call")
    facts = _gold_facts(value["gold_facts"], "gold_facts")
    documents = value["knowledge_document_ids"]
    if (
        not isinstance(documents, list)
        or len(set(documents)) != len(documents)
        or any(type(item) is not int or item < 1 for item in documents)
    ):
        raise ValueError("knowledge_document_ids must be unique positive integers")
    maxima = {
        "max_model_calls": budget.max_model_calls,
        "max_tool_calls": budget.max_tool_calls,
        "max_total_tokens": budget.max_total_tokens,
    }
    for name, maximum in maxima.items():
        item = value[name]
        if type(item) is not int or not 0 <= item <= maximum:
            raise ValueError(f"Agent evaluation {name} exceeds the frozen budget")
    return {
        "status": status,
        "reason_prefix": reason_prefix,
        "first_tool": first_tool,
        "required_tools": required,
        "forbidden_tools": forbidden,
        "required_evidence_tools": evidence,
        "gold_facts": facts,
        "knowledge_document_ids": copy.deepcopy(documents),
        "max_model_calls": value["max_model_calls"],
        "max_tool_calls": value["max_tool_calls"],
        "max_total_tokens": value["max_total_tokens"],
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
                "Agent evaluation gold must identify one replayed fact: "
                + canonical(expected)
            )
        identifiers.append(matches[0])
    return identifiers


def _load_spec(path: Path, budget: AgentBudget) -> dict[str, Any]:
    spec = read(path)
    if set(spec) != {"evaluation_id", "split", "formation", "cases"}:
        raise ValueError("Agent evaluation specification has invalid fields")
    if (
        not isinstance(spec["evaluation_id"], str)
        or not spec["evaluation_id"]
        or spec["split"] != "held-out"
        or not isinstance(spec["formation"], str)
        or not spec["formation"]
        or not isinstance(spec["cases"], list)
        or not spec["cases"]
    ):
        raise ValueError("Agent evaluation specification metadata is invalid")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in spec["cases"]:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "category", "report", "goal", "expected"}
        ):
            raise ValueError("Agent evaluation case has invalid fields")
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
            raise ValueError("Agent evaluation case metadata is invalid")
        seen.add(case_id)
        cases.append(
            {
                **copy.deepcopy(case),
                "goal": case["goal"].strip(),
                "expected": _validate_expected(case["expected"], budget),
            }
        )
    return {**copy.deepcopy(spec), "cases": cases}


def freeze_agent_evaluation(
    root: Path,
    implementation_root: Path,
    spec_path: Path,
    output: Path,
    *,
    model: str,
    model_digest: str,
    budget: AgentBudget,
    knowledge_policy_path: str | None = None,
) -> dict[str, Any]:
    """Freeze replayed evidence and structural gold before any model inference."""
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evaluation manifest output must be absent")
    if not model or not re.fullmatch(r"[0-9a-f]{64}", model_digest):
        raise ValueError("Agent evaluation model identity is invalid")
    spec = _load_spec(spec_path, budget)
    policy_binding: dict[str, Any] | None = None
    if knowledge_policy_path is not None:
        policy_path = _resolve(root, knowledge_policy_path, "Knowledge policy")
        policy = validate_agent_knowledge_policy(read(policy_path))
        policy_binding = {
            "path": knowledge_policy_path,
            "sha256": _sha256(policy_path),
            "policy_id": policy["policy_id"],
        }
    cases: list[dict[str, Any]] = []
    for case in spec["cases"]:
        report = _resolve(root, case["report"], "Agent evaluation report")
        request = build_request(report, case["goal"])
        expected = copy.deepcopy(case["expected"])
        expected["gold_fact_ids"] = _gold_fact_ids(
            request, expected.pop("gold_facts")
        )
        if expected["knowledge_document_ids"] and policy_binding is None:
            raise ValueError("Knowledge gold requires a frozen Agent knowledge policy")
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
        "artifact_type": "readonly-agent-evaluation-manifest",
        "schema_version": MANIFEST_VERSION,
        "evaluation_id": spec["evaluation_id"],
        "split": spec["split"],
        "formation": spec["formation"],
        "spec_sha256": digest(spec),
        "implementation_sha256": implementation_digest(implementation_root),
        "model": {"name": model, "digest": model_digest},
        "knowledge_policy": policy_binding,
        "budget": budget.as_dict(),
        "cases": cases,
        "boundary": MANIFEST_BOUNDARY,
    }
    manifest = {"manifest_id": digest(body), **body}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


def load_agent_evaluation_manifest(path: Path) -> dict[str, Any]:
    manifest = read(path)
    fields = {
        "manifest_id",
        "artifact_type",
        "schema_version",
        "evaluation_id",
        "split",
        "formation",
        "spec_sha256",
        "implementation_sha256",
        "model",
        "knowledge_policy",
        "budget",
        "cases",
        "boundary",
    }
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ValueError("Invalid Agent evaluation manifest fields")
    if (
        manifest["artifact_type"] != "readonly-agent-evaluation-manifest"
        or manifest["schema_version"] != MANIFEST_VERSION
        or manifest["split"] != "held-out"
        or manifest["boundary"] != MANIFEST_BOUNDARY
        or manifest["manifest_id"]
        != digest({name: manifest[name] for name in manifest if name != "manifest_id"})
        or not isinstance(manifest["evaluation_id"], str)
        or not manifest["evaluation_id"]
        or not isinstance(manifest["formation"], str)
        or not manifest["formation"]
        or any(
            not isinstance(manifest[name], str)
            or not re.fullmatch(r"[0-9a-f]{64}", manifest[name])
            for name in ("spec_sha256", "implementation_sha256")
        )
        or not isinstance(manifest["model"], dict)
        or set(manifest["model"]) != {"name", "digest"}
        or not isinstance(manifest["model"]["name"], str)
        or not manifest["model"]["name"]
        or not isinstance(manifest["model"]["digest"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", manifest["model"]["digest"])
    ):
        raise ValueError("Invalid Agent evaluation manifest metadata")
    try:
        budget = AgentBudget(**manifest["budget"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Agent evaluation budget") from exc
    policy = manifest["knowledge_policy"]
    if policy is not None and (
        not isinstance(policy, dict)
        or set(policy) != {"path", "sha256", "policy_id"}
        or not isinstance(policy["path"], str)
        or not policy["path"]
        or any(
            not isinstance(policy[name], str)
            or not re.fullmatch(r"[0-9a-f]{64}", policy[name])
            for name in ("sha256", "policy_id")
        )
    ):
        raise ValueError("Invalid Agent evaluation knowledge policy binding")
    cases = manifest["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("Agent evaluation manifest requires cases")
    seen: set[str] = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case)
            != {
                "case_id",
                "category",
                "report",
                "report_sha256",
                "bundle_sha256",
                "goal",
                "expected",
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
                not isinstance(case[name], str)
                or not re.fullmatch(r"[0-9a-f]{64}", case[name])
                for name in ("report_sha256", "bundle_sha256")
            )
        ):
            raise ValueError("Invalid Agent evaluation case metadata")
        seen.add(case["case_id"])
        expected = copy.deepcopy(case["expected"])
        if not isinstance(expected, dict) or "gold_fact_ids" not in expected:
            raise ValueError("Invalid frozen Agent evaluation expectation")
        fact_ids = expected.pop("gold_fact_ids")
        expected["gold_facts"] = []
        _validate_expected(expected, budget)
        if (
            not isinstance(fact_ids, list)
            or len(set(fact_ids)) != len(fact_ids)
            or any(
                not isinstance(item, str)
                or not re.fullmatch(r"[0-9a-f]{64}", item)
                for item in fact_ids
            )
        ):
            raise ValueError("Invalid frozen Agent evaluation fact IDs")
    return manifest


def score_agent_trace(case: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    """Score structural behavior only; never use the final prose as a judge."""
    verify_agent_trace(trace)
    expected = case["expected"]
    tool_events = [
        event
        for event in trace["events"]
        if event["kind"] == "tool" and event["status"] == "passed"
    ]
    tool_sequence = [event["tool_name"] for event in tool_events]
    required = set(expected["required_tools"])
    forbidden = set(expected["forbidden_tools"])
    first_tool = tool_sequence[0] if tool_sequence else None
    tool_selection_passed = (
        required <= set(tool_sequence)
        and not forbidden.intersection(tool_sequence)
        and first_tool == expected["first_tool"]
    )
    selected_facts: set[str] = set()
    knowledge_documents: set[int] = set()
    observations_by_tool: dict[str, set[str]] = {}
    for event in tool_events:
        observation = event["observation_id"]
        observations_by_tool.setdefault(event["tool_name"], set()).add(observation)
        result = event["result"]
        if event["tool_name"] == "project_query_facts":
            selected_facts.update(
                fact["fact_id"]
                for fact in result.get("facts", [])
                if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str)
            )
        if event["tool_name"] == "knowledge_retrieve_reviewed":
            knowledge_documents.update(
                source["document_id"]
                for source in result.get("sources", [])
                if isinstance(source, dict) and type(source.get("document_id")) is int
            )
    gold = set(expected["gold_fact_ids"])
    required_documents = set(expected["knowledge_document_ids"])
    parameter_passed = gold <= selected_facts and required_documents <= knowledge_documents
    cited = set(trace["final"]["evidence_ids"]) if trace["final"] else set()
    evidence_tools = expected["required_evidence_tools"]
    citation_passed = all(
        observations_by_tool.get(tool, set()).intersection(cited)
        for tool in evidence_tools
    )
    if expected["status"] == "refused":
        citation_passed = trace["final"] is None
    status_passed = trace["status"] == expected["status"] and trace[
        "reason"
    ].startswith(expected["reason_prefix"])
    usage = trace["usage"]
    cost_passed = (
        usage["model_calls"] <= expected["max_model_calls"]
        and usage["tool_calls"] <= expected["max_tool_calls"]
        and usage["total_tokens"] <= expected["max_total_tokens"]
    )
    refusal_kind = "not-applicable"
    if expected["status"] == "refused":
        if trace["reason"].startswith("model_declined:"):
            refusal_kind = "model-declared"
        elif trace["status"] == "refused":
            refusal_kind = "runtime-guard"
        else:
            refusal_kind = "missing"
    checks = {
        "status": status_passed,
        "tool_selection": tool_selection_passed,
        "parameters": parameter_passed,
        "citation": citation_passed,
        "cost": cost_passed,
    }
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "status": "passed" if all(checks.values()) else "failed",
        "trace_id": trace["trace_id"],
        "agent_status": trace["status"],
        "agent_reason": trace["reason"],
        "tool_sequence": tool_sequence,
        "selected_gold_facts": len(gold & selected_facts),
        "required_gold_facts": len(gold),
        "gold_fact_recall": len(gold & selected_facts) / len(gold) if gold else None,
        "matched_knowledge_documents": sorted(
            required_documents & knowledge_documents
        ),
        "refusal_kind": refusal_kind,
        "checks": checks,
        "usage": copy.deepcopy(usage),
    }


def _result_body(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {name: sum(row["checks"][name] for row in rows) for name in (
        "status", "tool_selection", "parameters", "citation", "cost"
    )}
    body = {
        "artifact_type": "readonly-agent-evaluation-result",
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
            "total_tokens": sum(row["usage"]["total_tokens"] for row in rows),
            "model_calls": sum(row["usage"]["model_calls"] for row in rows),
            "tool_calls": sum(row["usage"]["tool_calls"] for row in rows),
        },
        "cases": rows,
        "boundary": RESULT_BOUNDARY,
    }
    return {"result_id": digest(body), **body}


def run_agent_evaluation(
    root: Path,
    implementation_root: Path,
    manifest_path: Path,
    expected_manifest_id: str,
    output: Path,
    *,
    client: ModelClient,
    knowledge_endpoint: ServiceEndpoint | None = None,
) -> dict[str, Any]:
    manifest = load_agent_evaluation_manifest(manifest_path)
    if manifest["manifest_id"] != expected_manifest_id:
        raise ValueError("Agent evaluation manifest ID differs from the frozen ID")
    if manifest["implementation_sha256"] != implementation_digest(implementation_root):
        raise ValueError("Agent evaluation implementation differs from the frozen code")
    if output.exists() or output.is_symlink():
        raise ValueError("Agent evaluation output must be absent")
    policy_binding = manifest["knowledge_policy"]
    policy: dict[str, Any] | None = None
    if policy_binding is not None:
        policy_path = _resolve(root, policy_binding["path"], "Knowledge policy")
        if _sha256(policy_path) != policy_binding["sha256"]:
            raise ValueError("Frozen Agent knowledge policy bytes changed")
        policy = load_agent_knowledge_policy(policy_path)
        if policy["policy_id"] != policy_binding["policy_id"]:
            raise ValueError("Frozen Agent knowledge policy identity changed")
        if knowledge_endpoint is None:
            raise ValueError("Frozen Agent evaluation requires a knowledge endpoint")
    elif knowledge_endpoint is not None:
        raise ValueError("Knowledge endpoint supplied without a frozen policy")
    reports: dict[str, Path] = {}
    for case in manifest["cases"]:
        report = _resolve(root, case["report"], "Agent evaluation report")
        request = build_request(report, case["goal"])
        if (
            request["report_sha256"] != case["report_sha256"]
            or _bundle_digest(report) != case["bundle_sha256"]
        ):
            raise ValueError("Frozen Agent evaluation evidence changed: " + case["case_id"])
        reports[case["case_id"]] = report
    output.mkdir(parents=True)
    traces = output / "traces"
    traces.mkdir()
    budget = AgentBudget(**manifest["budget"])
    rows: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        registry = build_readonly_registry(
            reports[case["case_id"]],
            knowledge_endpoint=knowledge_endpoint,
            knowledge_policy=policy,
        )
        trace = AgentRunner(client, registry, budget).run(
            case["goal"], manifest["model"]["name"]
        )
        if trace["model"] is not None and (
            trace["model"].get("name") != manifest["model"]["name"]
            or trace["model"].get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Agent evaluation model differs from the frozen identity")
        save_agent_trace(trace, traces / f"{case['case_id']}.json")
        row = score_agent_trace(case, trace)
        row["trace"] = f"traces/{case['case_id']}.json"
        rows.append(row)
        partial = {
            "complete": False,
            "evaluation_id": manifest["evaluation_id"],
            "manifest_id": manifest["manifest_id"],
            "cases": rows,
        }
        (output / "partial.json").write_text(
            canonical(partial) + "\n", encoding="utf-8", newline="\n"
        )
    result = _result_body(manifest, rows)
    (output / "evaluation.json").write_text(
        canonical(result) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def verify_agent_evaluation(
    manifest_path: Path, directory: Path
) -> dict[str, Any]:
    manifest = load_agent_evaluation_manifest(manifest_path)
    result = read(directory / "evaluation.json")
    fields = {
        "result_id",
        "artifact_type",
        "schema_version",
        "status",
        "evaluation_id",
        "manifest_id",
        "split",
        "model",
        "semantic_status",
        "summary",
        "cases",
        "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result["artifact_type"] != "readonly-agent-evaluation-result"
        or result["schema_version"] != RESULT_VERSION
        or result["boundary"] != RESULT_BOUNDARY
        or result["semantic_status"] != "unassessed"
        or result["evaluation_id"] != manifest["evaluation_id"]
        or result["manifest_id"] != manifest["manifest_id"]
        or result["split"] != manifest["split"]
        or canonical(result["model"]) != canonical(manifest["model"])
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
        or not isinstance(result["cases"], list)
        or len(result["cases"]) != len(manifest["cases"])
    ):
        raise ValueError("Invalid Agent evaluation result metadata")
    rows: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        if not isinstance(recorded, dict) or recorded.get("case_id") != case["case_id"]:
            raise ValueError("Agent evaluation result case order differs")
        relative = recorded.get("trace")
        if not isinstance(relative, str):
            raise ValueError("Agent evaluation result trace path is invalid")
        trace_path = _resolve(directory, relative, "Agent evaluation trace")
        trace = read(trace_path)
        if trace["model"] is not None and (
            trace["model"].get("name") != manifest["model"]["name"]
            or trace["model"].get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Agent evaluation trace model differs from the manifest")
        row = score_agent_trace(case, trace)
        row["trace"] = relative
        rows.append(row)
        if canonical(row) != canonical(recorded):
            raise ValueError("Agent evaluation result differs from trace scoring")
    expected = _result_body(manifest, rows)
    if canonical(expected) != canonical(result):
        raise ValueError("Agent evaluation result summary differs from traces")
    return {
        "status": "passed",
        "evaluation_status": result["status"],
        "result_id": result["result_id"],
        "manifest_id": manifest["manifest_id"],
        "case_count": len(rows),
    }
