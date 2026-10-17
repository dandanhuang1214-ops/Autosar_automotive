"""Freeze and score read-only preparation followed by deterministic admission."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_action_admission import (
    admit_action_candidates,
    issue_action_intent,
    verify_action_admission,
    verify_action_intent,
)
from automotive_workbench.agent_candidate_evaluation import (
    _action_template,
    _bundle_digest,
    _candidate_evidence_ids,
    _gold_fact_ids,
    _gold_facts,
    _issue_case_candidates,
    _resolve,
    _successful_tool_events,
)
from automotive_workbench.agent_proposal import build_restricted_action_catalog
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


MANIFEST_VERSION = "agent-admission-evaluation-manifest-0.1"
RESULT_VERSION = "agent-admission-evaluation-result-0.1"
MANIFEST_BOUNDARY = (
    "Cases, structural gold, typed intent, and exact action templates are frozen "
    "before target-model inference. The model can only prepare one read-only "
    "checkpoint; deterministic admission does not consult the model."
)
RESULT_BOUNDARY = (
    "Scoring is deterministic and artifact-based. The target model is measured "
    "only for read-only evidence preparation. Candidate issuance, typed intent, "
    "and admission use no model, authorize nothing, and invoke no action."
)
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_IMPLEMENTATION_FILES = (
    "scripts/run_agent_admission_evaluation.py",
    "schemas/agent-action-candidate.schema.json",
    "schemas/agent-action-intent.schema.json",
    "schemas/agent-action-admission.schema.json",
    "schemas/agent-admission-evaluation-manifest.schema.json",
    "schemas/agent-admission-evaluation-result.schema.json",
    "src/automotive_workbench/agent_admission_evaluation.py",
    "src/automotive_workbench/agent_action_admission.py",
    "src/automotive_workbench/agent_action_candidate.py",
    "src/automotive_workbench/agent_candidate_evaluation.py",
    "src/automotive_workbench/agent_runtime.py",
    "src/automotive_workbench/model_client.py",
    "src/automotive_workbench/project_explanation.py",
)
_EXPECTED_FIELDS = {
    "admission_status",
    "admission_reason",
    "selected_candidate_key",
    "first_read_tool",
    "gold_facts",
    "max_cumulative_model_calls",
    "max_cumulative_total_tokens",
}
_INTENT_FIELDS = {
    "disposition",
    "requested_capability",
    "requested_action_candidate_key",
    "evidence_conditions",
    "deterministic_decline_reason",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admission_evaluation_implementation_digest(root: Path) -> str:
    files = {
        relative: _sha256(_resolve(root, relative, "Admission evaluation implementation"))
        for relative in _IMPLEMENTATION_FILES
    }
    return digest(files)


def _validate_intent(value: Any, candidate_keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _INTENT_FIELDS:
        raise ValueError("Agent admission evaluation intent has invalid fields")
    disposition = value["disposition"]
    capability = value["requested_capability"]
    action_key = value["requested_action_candidate_key"]
    conditions = value["evidence_conditions"]
    reason = value["deterministic_decline_reason"]
    if disposition not in {"exact_action", "no_action", "unsupported_action"}:
        raise ValueError("Agent admission evaluation disposition is invalid")
    if not isinstance(conditions, list):
        raise ValueError("Agent admission evaluation conditions are invalid")
    checked_conditions: list[dict[str, Any]] = []
    for item in conditions:
        if (
            not isinstance(item, dict)
            or set(item) != {"fact", "expected_value"}
            or isinstance(item["expected_value"], (dict, list))
        ):
            raise ValueError("Agent admission evaluation condition is invalid")
        fact = _gold_facts([item["fact"]])[0]
        checked_conditions.append(
            {"fact": fact, "expected_value": copy.deepcopy(item["expected_value"])}
        )
    if len({canonical(item) for item in checked_conditions}) != len(checked_conditions):
        raise ValueError("Agent admission evaluation conditions contain duplicates")
    if disposition == "exact_action":
        if (
            capability
            != {
                "scope": "process_local_virtual",
                "interface": "virtual",
                "channel": None,
            }
            or not isinstance(action_key, str)
            or action_key not in candidate_keys
            or not checked_conditions
            or reason is not None
        ):
            raise ValueError("Agent admission evaluation exact intent is invalid")
    elif disposition == "no_action":
        if (
            capability is not None
            or action_key is not None
            or checked_conditions
            or reason != "action_not_required"
        ):
            raise ValueError("Agent admission evaluation no-action intent is invalid")
    else:
        valid_unsupported = (
            isinstance(capability, dict)
            and set(capability) == {"scope", "interface", "channel"}
            and (
                (
                    capability["scope"] == "host_socketcan"
                    and capability["interface"] == "socketcan"
                )
                or (
                    capability["scope"] == "hardware"
                    and capability["interface"] == "hardware"
                )
            )
            and isinstance(capability["channel"], str)
            and bool(capability["channel"])
        )
        if (
            not valid_unsupported
            or action_key is not None
            or checked_conditions
            or reason != "outside_restricted_capabilities"
        ):
            raise ValueError("Agent admission evaluation unsupported intent is invalid")
    return {
        "disposition": disposition,
        "requested_capability": copy.deepcopy(capability),
        "requested_action_candidate_key": action_key,
        "evidence_conditions": checked_conditions,
        "deterministic_decline_reason": reason,
    }


def _validate_expected(
    value: Any, budget: AgentBudget, candidate_keys: set[str]
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _EXPECTED_FIELDS:
        raise ValueError("Agent admission evaluation expectation has invalid fields")
    status = value["admission_status"]
    reason = value["admission_reason"]
    selected_key = value["selected_candidate_key"]
    if status not in {"approval_required", "declined", "refused"}:
        raise ValueError("Expected Agent admission status is invalid")
    if not isinstance(reason, str) or not reason:
        raise ValueError("Expected Agent admission reason is invalid")
    if status == "approval_required":
        if (
            reason != "control_plane_exact_candidate_admitted"
            or not isinstance(selected_key, str)
            or selected_key not in candidate_keys
        ):
            raise ValueError("Expected admitted candidate is invalid")
    elif selected_key is not None:
        raise ValueError("Expected declined/refused candidate must be null")
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
        "admission_status": status,
        "admission_reason": reason,
        "selected_candidate_key": selected_key,
        "first_read_tool": first_tool,
        "gold_facts": _gold_facts(value["gold_facts"]),
        "max_cumulative_model_calls": calls,
        "max_cumulative_total_tokens": tokens,
    }


def _load_spec(
    path: Path, budget: AgentBudget
) -> dict[str, Any]:
    spec = read(path)
    if set(spec) != {"evaluation_id", "split", "formation", "cases"}:
        raise ValueError("Agent admission evaluation specification has invalid fields")
    if (
        not isinstance(spec["evaluation_id"], str)
        or not spec["evaluation_id"]
        or spec["split"] != "held-out"
        or not isinstance(spec["formation"], str)
        or not spec["formation"]
        or not isinstance(spec["cases"], list)
        or not spec["cases"]
    ):
        raise ValueError("Agent admission evaluation specification metadata is invalid")
    catalog = build_restricted_action_catalog()
    cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for case in spec["cases"]:
        if (
            not isinstance(case, dict)
            or set(case)
            != {"case_id", "category", "report", "goal", "candidates", "intent", "expected"}
        ):
            raise ValueError("Agent admission evaluation case has invalid fields")
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
            raise ValueError("Agent admission evaluation case metadata is invalid")
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
                raise ValueError("Agent admission evaluation candidate is invalid")
            keys.add(item["candidate_key"])
            candidates.append(
                {
                    "candidate_key": item["candidate_key"],
                    "action": _action_template(catalog, item["tool_name"], item["arguments"]),
                    "evidence_gold_facts": _gold_facts(item["evidence_gold_facts"]),
                }
            )
        cases.append(
            {
                "case_id": case_id,
                "category": case["category"],
                "report": case["report"],
                "goal": case["goal"].strip(),
                "candidates": candidates,
                "intent": _validate_intent(case["intent"], keys),
                "expected": _validate_expected(case["expected"], budget, keys),
            }
        )
    return {**copy.deepcopy(spec), "cases": cases}


def freeze_agent_admission_evaluation(
    root: Path,
    implementation_root: Path,
    spec_path: Path,
    output: Path,
    *,
    model: str,
    model_digest: str,
    budget: AgentBudget,
) -> dict[str, Any]:
    """Freeze the read-only cohort and deterministic control-plane expectations."""
    if output.exists() or output.is_symlink():
        raise ValueError("Agent admission evaluation manifest output must be absent")
    if not model or not _HEX.fullmatch(model_digest):
        raise ValueError("Agent admission evaluation model identity is invalid")
    spec = _load_spec(spec_path, budget)
    cases: list[dict[str, Any]] = []
    for case in spec["cases"]:
        report = _resolve(root, case["report"], "Agent admission evaluation report")
        request = build_request(report, case["goal"])
        expected = copy.deepcopy(case["expected"])
        expected["gold_fact_ids"] = _gold_fact_ids(request, expected.pop("gold_facts"))
        candidates = [
            {
                "candidate_key": item["candidate_key"],
                "action": copy.deepcopy(item["action"]),
                "evidence_fact_ids": _gold_fact_ids(request, item["evidence_gold_facts"]),
            }
            for item in case["candidates"]
        ]
        intent = copy.deepcopy(case["intent"])
        intent["evidence_conditions"] = [
            {
                "fact_id": _gold_fact_ids(request, [item["fact"]])[0],
                "expected_value": copy.deepcopy(item["expected_value"]),
            }
            for item in intent["evidence_conditions"]
        ]
        cases.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "report": case["report"],
                "report_sha256": request["report_sha256"],
                "bundle_sha256": _bundle_digest(report),
                "goal": case["goal"],
                "candidates": candidates,
                "intent": intent,
                "expected": expected,
            }
        )
    body = {
        "artifact_type": "agent-admission-evaluation-manifest",
        "schema_version": MANIFEST_VERSION,
        "evaluation_id": spec["evaluation_id"],
        "split": spec["split"],
        "formation": spec["formation"],
        "spec_sha256": digest(read(spec_path)),
        "implementation_sha256": admission_evaluation_implementation_digest(implementation_root),
        "model": {"name": model, "digest": model_digest},
        "budget": budget.as_dict(),
        "cases": cases,
        "boundary": MANIFEST_BOUNDARY,
    }
    manifest = {"manifest_id": digest(body), **body}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


def load_agent_admission_evaluation_manifest(path: Path) -> dict[str, Any]:
    manifest = read(path)
    fields = {
        "manifest_id", "artifact_type", "schema_version", "evaluation_id",
        "split", "formation", "spec_sha256", "implementation_sha256",
        "model", "budget", "cases", "boundary",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != fields
        or manifest.get("artifact_type") != "agent-admission-evaluation-manifest"
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
        raise ValueError("Invalid Agent admission evaluation manifest metadata")
    try:
        budget = AgentBudget(**manifest["budget"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Agent admission evaluation budget") from exc
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Agent admission evaluation manifest requires cases")
    catalog = build_restricted_action_catalog()
    seen: set[str] = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case)
            != {
                "case_id", "category", "report", "report_sha256", "bundle_sha256",
                "goal", "candidates", "intent", "expected",
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
            raise ValueError("Invalid Agent admission evaluation case metadata")
        seen.add(case["case_id"])
        candidates = case.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Invalid frozen Agent admission candidates")
        keys: set[str] = set()
        for item in candidates:
            if (
                not isinstance(item, dict)
                or set(item) != {"candidate_key", "action", "evidence_fact_ids"}
                or not isinstance(item["candidate_key"], str)
                or not _CASE_ID.fullmatch(item["candidate_key"])
                or item["candidate_key"] in keys
                or not isinstance(item["evidence_fact_ids"], list)
                or not item["evidence_fact_ids"]
                or len(set(item["evidence_fact_ids"])) != len(item["evidence_fact_ids"])
                or any(not isinstance(x, str) or not _HEX.fullmatch(x) for x in item["evidence_fact_ids"])
            ):
                raise ValueError("Invalid frozen Agent admission candidate")
            action = item.get("action")
            if (
                not isinstance(action, dict)
                or action
                != _action_template(
                    catalog, action.get("tool_name"), action.get("arguments")
                )
            ):
                raise ValueError("Invalid frozen Agent admission candidate")
            keys.add(item["candidate_key"])
        intent = case.get("intent")
        if not isinstance(intent, dict) or set(intent) != _INTENT_FIELDS:
            raise ValueError("Invalid frozen Agent admission intent")
        conditions = intent.get("evidence_conditions")
        if not isinstance(conditions, list) or any(
            not isinstance(item, dict)
            or set(item) != {"fact_id", "expected_value"}
            or not isinstance(item["fact_id"], str)
            or not _HEX.fullmatch(item["fact_id"])
            or isinstance(item["expected_value"], (dict, list))
            for item in conditions
        ):
            raise ValueError("Invalid frozen Agent admission intent conditions")
        spec_intent = copy.deepcopy(intent)
        spec_intent["evidence_conditions"] = [
            {
                "fact": {"artifact_id": "frozen", "pointer": "/frozen", "value": item["fact_id"]},
                "expected_value": item["expected_value"],
            }
            for item in conditions
        ]
        _validate_intent(spec_intent, keys)
        expected = copy.deepcopy(case.get("expected"))
        if not isinstance(expected, dict) or "gold_fact_ids" not in expected:
            raise ValueError("Invalid frozen Agent admission expectation")
        fact_ids = expected.pop("gold_fact_ids")
        if (
            not isinstance(fact_ids, list)
            or not fact_ids
            or len(set(fact_ids)) != len(fact_ids)
            or any(not isinstance(item, str) or not _HEX.fullmatch(item) for item in fact_ids)
        ):
            raise ValueError("Invalid frozen Agent admission fact IDs")
        expected["gold_facts"] = [
            {"artifact_id": "frozen", "pointer": "/frozen", "value": item}
            for item in fact_ids
        ]
        _validate_expected(expected, budget, keys)
    return manifest


def _runtime_intent(
    checkpoint: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    frozen = case["intent"]
    conditions: list[dict[str, Any]] = []
    for item in frozen["evidence_conditions"]:
        evidence_ids = _candidate_evidence_ids(checkpoint, [item["fact_id"]])
        if evidence_ids is None or len(evidence_ids) != 1:
            raise ValueError("Agent admission intent fact is absent from one observation")
        conditions.append(
            {
                "observation_id": evidence_ids[0],
                "selector": {"kind": "fact_id", "value": item["fact_id"]},
                "expected_value": copy.deepcopy(item["expected_value"]),
            }
        )
    action_key = frozen["requested_action_candidate_key"]
    requested_action = None
    if action_key is not None:
        template = next(item for item in case["candidates"] if item["candidate_key"] == action_key)
        requested_action = {
            "tool_name": template["action"]["tool_name"],
            "arguments": copy.deepcopy(template["action"]["arguments"]),
        }
    return issue_action_intent(
        checkpoint,
        {
            "disposition": frozen["disposition"],
            "requested_capability": copy.deepcopy(frozen["requested_capability"]),
            "requested_action": requested_action,
            "evidence_conditions": conditions,
            "deterministic_decline_reason": frozen["deterministic_decline_reason"],
        },
    )


def score_agent_admission_case(
    case: dict[str, Any],
    preparation: dict[str, Any],
    candidates: list[tuple[str, dict[str, Any]]],
    intent: dict[str, Any] | None,
    admission: dict[str, Any] | None,
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
    preparation_check = is_checkpoint and first_tool == expected["first_read_tool"] and gold <= selected_facts
    candidate_check = False
    if is_checkpoint and len(candidates) == len(case["candidates"]):
        candidate_check = all(
            key == template["candidate_key"]
            and candidate["action"] == template["action"]
            and candidate["evidence_ids"]
            == _candidate_evidence_ids(preparation, template["evidence_fact_ids"])
            for template, (key, candidate) in zip(case["candidates"], candidates, strict=True)
        )
    intent_check = admission_status_check = resolution_check = False
    evidence_check = boundary_check = False
    admission_status = admission_reason = selected_key = None
    requested_action = None
    if is_checkpoint and candidate_check and intent is not None and admission is not None:
        verify_action_intent(preparation, intent)
        values = [item for _, item in candidates]
        verify_action_admission(preparation, intent, values, admission)
        expected_intent = _runtime_intent(preparation, case)
        intent_check = intent == expected_intent
        admission_status = admission["status"]
        admission_reason = admission["reason"]
        requested_action = copy.deepcopy(admission["requested_action"])
        by_id = {item["candidate_id"]: key for key, item in candidates}
        selected_key = by_id.get(admission["selected_candidate_id"])
        admission_status_check = (
            admission_status == expected["admission_status"]
            and admission_reason == expected["admission_reason"]
        )
        resolution_check = selected_key == expected["selected_candidate_key"]
        if expected["selected_candidate_key"] is None:
            resolution_check = resolution_check and requested_action is None
        else:
            expected_action = next(
                item["action"]
                for item in case["candidates"]
                if item["candidate_key"] == expected["selected_candidate_key"]
            )
            resolution_check = resolution_check and requested_action == expected_action
        evidence_check = (
            admission["evidence_ids"]
            == sorted({item["observation_id"] for item in intent["evidence_conditions"]})
            and all(
                item["observation_id"] in admission["evidence_ids"]
                for item in admission["evaluated_conditions"]
            )
        )
        boundary_check = (
            admission["model_invoked"] is False
            and admission["execution_authorized"] is False
            and admission["tool_invoked"] is False
            and intent["execution_authorized"] is False
            and intent["tool_invoked"] is False
            and all(
                candidate["execution_authorized"] is False
                and candidate["tool_invoked"] is False
                for _, candidate in candidates
            )
        )
    usage = copy.deepcopy(preparation["usage"])
    cost_check = (
        usage.get("cumulative_model_calls", usage["model_calls"])
        <= expected["max_cumulative_model_calls"]
        and usage.get("cumulative_total_tokens", usage["total_tokens"])
        <= expected["max_cumulative_total_tokens"]
    )
    checks = {
        "checkpoint_preparation": preparation_check,
        "candidate_issuance": candidate_check,
        "intent_issuance": intent_check,
        "admission_status": admission_status_check,
        "candidate_resolution": resolution_check,
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
            {"candidate_key": key, "candidate_id": candidate["candidate_id"], "action": copy.deepcopy(candidate["action"])}
            for key, candidate in candidates
        ],
        "intent_disposition": intent.get("disposition") if intent is not None else None,
        "admission_status": admission_status,
        "admission_reason": admission_reason,
        "selected_candidate_key": selected_key,
        "requested_action": requested_action,
        "checks": checks,
        "usage": usage,
    }


def _result_body(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    check_names = (
        "checkpoint_preparation", "candidate_issuance", "intent_issuance",
        "admission_status", "candidate_resolution", "evidence_binding",
        "non_execution_boundary", "cost",
    )
    totals = {name: sum(row["checks"][name] for row in rows) for name in check_names}
    body = {
        "artifact_type": "agent-admission-evaluation-result",
        "schema_version": RESULT_VERSION,
        "status": "passed" if all(row["status"] == "passed" for row in rows) else "failed",
        "evaluation_id": manifest["evaluation_id"],
        "manifest_id": manifest["manifest_id"],
        "split": manifest["split"],
        "model": copy.deepcopy(manifest["model"]),
        "model_role": "read_only_evidence_preparation",
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


def run_agent_admission_evaluation(
    root: Path,
    implementation_root: Path,
    manifest_path: Path,
    expected_manifest_id: str,
    output: Path,
    *,
    client: ModelClient,
) -> dict[str, Any]:
    manifest = load_agent_admission_evaluation_manifest(manifest_path)
    if manifest["manifest_id"] != expected_manifest_id:
        raise ValueError("Agent admission manifest ID differs from the frozen ID")
    if manifest["implementation_sha256"] != admission_evaluation_implementation_digest(implementation_root):
        raise ValueError("Agent admission evaluation implementation differs from frozen code")
    if output.exists() or output.is_symlink():
        raise ValueError("Agent admission evaluation output must be absent")
    reports: dict[str, Path] = {}
    for case in manifest["cases"]:
        report = _resolve(root, case["report"], "Agent admission evaluation report")
        request = build_request(report, case["goal"])
        if request["report_sha256"] != case["report_sha256"] or _bundle_digest(report) != case["bundle_sha256"]:
            raise ValueError("Frozen Agent admission evidence changed: " + case["case_id"])
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
        model = preparation.get("model")
        if model is not None and (
            model.get("name") != manifest["model"]["name"]
            or model.get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Agent admission evaluation model differs from frozen identity")
        preparation_name = f"{case['case_id']}-preparation.json"
        (artifacts / preparation_name).write_text(canonical(preparation) + "\n", encoding="utf-8", newline="\n")
        candidates: list[tuple[str, dict[str, Any]]] = []
        intent = admission = None
        candidate_paths: list[dict[str, str]] = []
        intent_name = admission_name = None
        if preparation.get("schema_version") == "readonly-agent-checkpoint-0.1":
            candidates = _issue_case_candidates(preparation, case)
            for key, candidate in candidates:
                name = f"{case['case_id']}-candidate-{key}.json"
                (artifacts / name).write_text(canonical(candidate) + "\n", encoding="utf-8", newline="\n")
                candidate_paths.append({"candidate_key": key, "artifact": f"artifacts/{name}"})
            if len(candidates) == len(case["candidates"]):
                intent = _runtime_intent(preparation, case)
                intent_name = f"{case['case_id']}-intent.json"
                (artifacts / intent_name).write_text(canonical(intent) + "\n", encoding="utf-8", newline="\n")
                admission = admit_action_candidates(preparation, intent, [item for _, item in candidates])
                admission_name = f"{case['case_id']}-admission.json"
                (artifacts / admission_name).write_text(canonical(admission) + "\n", encoding="utf-8", newline="\n")
        row = score_agent_admission_case(case, preparation, candidates, intent, admission)
        row["preparation_artifact"] = f"artifacts/{preparation_name}"
        row["candidate_artifacts"] = candidate_paths
        row["intent_artifact"] = f"artifacts/{intent_name}" if intent_name else None
        row["admission_artifact"] = f"artifacts/{admission_name}" if admission_name else None
        rows.append(row)
        (output / "partial.json").write_text(
            canonical({"complete": False, "evaluation_id": manifest["evaluation_id"], "manifest_id": manifest["manifest_id"], "cases": rows}) + "\n",
            encoding="utf-8", newline="\n",
        )
    result = _result_body(manifest, rows)
    (output / "evaluation.json").write_text(canonical(result) + "\n", encoding="utf-8", newline="\n")
    return result


def verify_agent_admission_evaluation(manifest_path: Path, directory: Path) -> dict[str, Any]:
    manifest = load_agent_admission_evaluation_manifest(manifest_path)
    result = read(directory / "evaluation.json")
    fields = {
        "result_id", "artifact_type", "schema_version", "status", "evaluation_id",
        "manifest_id", "split", "model", "model_role", "summary", "cases", "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result.get("artifact_type") != "agent-admission-evaluation-result"
        or result.get("schema_version") != RESULT_VERSION
        or result.get("boundary") != RESULT_BOUNDARY
        or result.get("model_role") != "read_only_evidence_preparation"
        or result.get("evaluation_id") != manifest["evaluation_id"]
        or result.get("manifest_id") != manifest["manifest_id"]
        or result.get("split") != manifest["split"]
        or result.get("model") != manifest["model"]
        or result.get("result_id") != digest({name: result[name] for name in result if name != "result_id"})
        or not isinstance(result.get("cases"), list)
        or len(result["cases"]) != len(manifest["cases"])
    ):
        raise ValueError("Invalid Agent admission evaluation result metadata")
    rows: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        if not isinstance(recorded, dict) or recorded.get("case_id") != case["case_id"]:
            raise ValueError("Agent admission evaluation result case order differs")
        preparation_relative = recorded.get("preparation_artifact")
        candidate_artifacts = recorded.get("candidate_artifacts")
        intent_relative = recorded.get("intent_artifact")
        admission_relative = recorded.get("admission_artifact")
        if (
            not isinstance(preparation_relative, str)
            or not isinstance(candidate_artifacts, list)
            or (intent_relative is not None and not isinstance(intent_relative, str))
            or (admission_relative is not None and not isinstance(admission_relative, str))
        ):
            raise ValueError("Agent admission evaluation artifact path is invalid")
        preparation = read(_resolve(directory, preparation_relative, "Preparation artifact"))
        candidates: list[tuple[str, dict[str, Any]]] = []
        for item in candidate_artifacts:
            if (
                not isinstance(item, dict)
                or set(item) != {"candidate_key", "artifact"}
                or not isinstance(item["candidate_key"], str)
                or not isinstance(item["artifact"], str)
            ):
                raise ValueError("Agent admission evaluation artifact path is invalid")
            candidates.append((item["candidate_key"], read(_resolve(directory, item["artifact"], "Candidate artifact"))))
        intent = read(_resolve(directory, intent_relative, "Intent artifact")) if intent_relative else None
        admission = read(_resolve(directory, admission_relative, "Admission artifact")) if admission_relative else None
        row = score_agent_admission_case(case, preparation, candidates, intent, admission)
        row["preparation_artifact"] = preparation_relative
        row["candidate_artifacts"] = candidate_artifacts
        row["intent_artifact"] = intent_relative
        row["admission_artifact"] = admission_relative
        if canonical(row) != canonical(recorded):
            raise ValueError("Agent admission evaluation result differs from artifact scoring")
        rows.append(row)
    expected = _result_body(manifest, rows)
    if canonical(expected) != canonical(result):
        raise ValueError("Agent admission evaluation summary differs from artifacts")
    return {
        "status": "passed",
        "evaluation_status": result["status"],
        "result_id": result["result_id"],
        "manifest_id": manifest["manifest_id"],
        "case_count": len(rows),
    }
