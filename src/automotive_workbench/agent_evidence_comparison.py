"""Freeze and replay pre-inference reference comparisons for evidence-plan summaries."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_evidence_plan import (
    build_agent_evidence_plan,
    run_agent_evidence_plan,
    save_agent_evidence_plan_result,
    verify_agent_evidence_plan,
    verify_agent_evidence_plan_result,
)
from automotive_workbench.agent_runtime import (
    AgentBudget,
    build_readonly_registry,
)
from automotive_workbench.explanation_services import ServiceEndpoint
from automotive_workbench.knowledge_policy import (
    load_agent_knowledge_policy,
    validate_agent_knowledge_policy,
)
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_explanation import canonical, digest, read

MANIFEST_VERSION = "agent-evidence-comparison-manifest-0.1"
RESULT_VERSION = "agent-evidence-comparison-result-0.1"
MANIFEST_BOUNDARY = (
    "Agent-authored reference answers and review criteria are frozen before target-model "
    "inference. They are not independent human gold and are never sent to the model."
)
RESULT_BOUNDARY = (
    "Structural scoring verifies the frozen evidence plan, model identity, citations, and "
    "cost. Target prose is presented beside the pre-inference reference but remains pending "
    "explicit comparative review."
)
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMPLEMENTATION_FILES = (
    "src/automotive_workbench/agent_evidence_comparison.py",
    "src/automotive_workbench/agent_evidence_plan.py",
    "src/automotive_workbench/agent_runtime.py",
    "src/automotive_workbench/model_client.py",
    "src/automotive_workbench/knowledge_policy.py",
    "src/automotive_workbench/project_explanation.py",
    "scripts/run_agent_evidence_comparison.py",
    "schemas/agent-evidence-comparison-manifest.schema.json",
    "schemas/agent-evidence-comparison-result.schema.json",
    "schemas/agent-evidence-plan.schema.json",
    "schemas/agent-evidence-plan-result.schema.json",
)


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
        raise ValueError(f"{label} escapes the comparison root")
    return path


def _bundle_digest(report: Path) -> str:
    files: dict[str, str] = {}
    for path in sorted(report.parent.rglob("*")):
        if path.is_symlink():
            raise ValueError("Evidence comparison bundles cannot contain symlinks")
        if path.is_file():
            files[path.relative_to(report.parent).as_posix()] = _sha256(path)
    if not files:
        raise ValueError("Evidence comparison report bundle is empty")
    return digest(files)


def comparison_implementation_digest(root: Path) -> str:
    files = {
        relative: _sha256(_resolve(root, relative, "Comparison implementation"))
        for relative in _IMPLEMENTATION_FILES
    }
    return digest(files)


def _binding(root: Path, relative: str, label: str) -> dict[str, Any]:
    path = _resolve(root, relative, label)
    value = read(path)
    return {"path": relative, "sha256": _sha256(path), "value": value}


def _criteria(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("Comparison criteria must be a nonempty array")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"criterion_id", "description"}
            or not isinstance(item["criterion_id"], str)
            or not _CASE_ID.fullmatch(item["criterion_id"])
            or item["criterion_id"] in seen
            or not isinstance(item["description"], str)
            or not item["description"].strip()
        ):
            raise ValueError("Invalid comparison criterion")
        seen.add(item["criterion_id"])
        result.append(
            {
                "criterion_id": item["criterion_id"],
                "description": item["description"].strip(),
            }
        )
    return result


def _load_spec(path: Path) -> dict[str, Any]:
    spec = read(path)
    if not isinstance(spec, dict) or set(spec) != {
        "comparison_id",
        "formation",
        "reference_author",
        "reference_boundary",
        "cases",
    }:
        raise ValueError("Evidence comparison specification has invalid fields")
    if (
        not isinstance(spec["comparison_id"], str)
        or not spec["comparison_id"]
        or not isinstance(spec["formation"], str)
        or not spec["formation"].strip()
        or not isinstance(spec["reference_author"], str)
        or not spec["reference_author"].strip()
        or not isinstance(spec["reference_boundary"], str)
        or not spec["reference_boundary"].strip()
        or not isinstance(spec["cases"], list)
        or not spec["cases"]
    ):
        raise ValueError("Evidence comparison specification metadata is invalid")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in spec["cases"]:
        if not isinstance(case, dict) or set(case) != {
            "case_id",
            "category",
            "report",
            "goal",
            "scope",
            "reference_answer",
            "criteria",
        }:
            raise ValueError("Evidence comparison case has invalid fields")
        case_id = case["case_id"]
        if (
            not isinstance(case_id, str)
            or not _CASE_ID.fullmatch(case_id)
            or case_id in seen
            or not isinstance(case["category"], str)
            or not case["category"].strip()
            or not isinstance(case["report"], str)
            or not case["report"]
            or not isinstance(case["goal"], str)
            or not 0 < len(case["goal"].strip()) <= 2000
            or not isinstance(case["reference_answer"], str)
            or not 0 < len(case["reference_answer"].strip()) <= 4000
        ):
            raise ValueError("Evidence comparison case metadata is invalid")
        plan = build_agent_evidence_plan(case["goal"], case["scope"])
        seen.add(case_id)
        cases.append(
            {
                **copy.deepcopy(case),
                "goal": plan["goal"],
                "scope": plan["scope"],
                "reference_answer": case["reference_answer"].strip(),
                "criteria": _criteria(case["criteria"]),
            }
        )
    return {**copy.deepcopy(spec), "cases": cases}


def freeze_agent_evidence_comparison(
    root: Path,
    implementation_root: Path,
    spec_path: Path,
    output: Path,
    *,
    model: str,
    model_digest: str,
    budget: AgentBudget,
    knowledge_policy_path: str,
    knowledge_corpus_path: str,
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Evidence comparison manifest output must be absent")
    if not model or not _SHA256.fullmatch(model_digest):
        raise ValueError("Evidence comparison model identity is invalid")
    spec = _load_spec(spec_path)
    policy_binding = _binding(root, knowledge_policy_path, "Knowledge policy")
    policy = validate_agent_knowledge_policy(policy_binding.pop("value"))
    policy_binding["policy_id"] = policy["policy_id"]
    corpus_binding = _binding(root, knowledge_corpus_path, "Knowledge corpus")
    corpus = corpus_binding.pop("value")
    if (
        not isinstance(corpus, dict)
        or corpus.get("schema_version") != "agent-reviewed-knowledge-corpus-0.1"
        or not isinstance(corpus.get("corpus_id"), str)
        or not _SHA256.fullmatch(corpus["corpus_id"])
    ):
        raise ValueError("Evidence comparison knowledge corpus is invalid")
    corpus_binding["corpus_id"] = corpus["corpus_id"]
    cases: list[dict[str, Any]] = []
    for case in spec["cases"]:
        report = _resolve(root, case["report"], "Evidence comparison report")
        plan = build_agent_evidence_plan(case["goal"], case["scope"])
        if (
            "reviewed_knowledge" in case["scope"]
            and policy_binding is None
        ):
            raise ValueError("Reviewed-knowledge scope requires frozen knowledge")
        cases.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "report": case["report"],
                "report_sha256": _sha256(report),
                "bundle_sha256": _bundle_digest(report),
                "plan": plan,
                "reference_answer": case["reference_answer"],
                "criteria": case["criteria"],
            }
        )
    body = {
        "artifact_type": "agent-evidence-comparison-manifest",
        "schema_version": MANIFEST_VERSION,
        "comparison_id": spec["comparison_id"],
        "formation": spec["formation"].strip(),
        "reference_author": spec["reference_author"].strip(),
        "reference_boundary": spec["reference_boundary"].strip(),
        "spec_sha256": digest(spec),
        "implementation_sha256": comparison_implementation_digest(
            implementation_root
        ),
        "model": {"name": model, "digest": model_digest},
        "knowledge_policy": policy_binding,
        "knowledge_corpus": corpus_binding,
        "budget": budget.as_dict(),
        "cases": cases,
        "boundary": MANIFEST_BOUNDARY,
    }
    manifest = {"manifest_id": digest(body), **body}
    verify_agent_evidence_comparison_manifest(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


def verify_agent_evidence_comparison_manifest(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "manifest_id",
        "artifact_type",
        "schema_version",
        "comparison_id",
        "formation",
        "reference_author",
        "reference_boundary",
        "spec_sha256",
        "implementation_sha256",
        "model",
        "knowledge_policy",
        "knowledge_corpus",
        "budget",
        "cases",
        "boundary",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != fields
        or manifest["artifact_type"] != "agent-evidence-comparison-manifest"
        or manifest["schema_version"] != MANIFEST_VERSION
        or manifest["boundary"] != MANIFEST_BOUNDARY
        or manifest["manifest_id"]
        != digest({name: manifest[name] for name in manifest if name != "manifest_id"})
        or any(
            not isinstance(manifest[name], str) or not manifest[name]
            for name in (
                "comparison_id",
                "formation",
                "reference_author",
                "reference_boundary",
            )
        )
        or any(
            not isinstance(manifest[name], str)
            or not _SHA256.fullmatch(manifest[name])
            for name in ("spec_sha256", "implementation_sha256")
        )
        or not isinstance(manifest["model"], dict)
        or set(manifest["model"]) != {"name", "digest"}
        or not isinstance(manifest["model"]["name"], str)
        or not manifest["model"]["name"]
        or not isinstance(manifest["model"]["digest"], str)
        or not _SHA256.fullmatch(manifest["model"]["digest"])
    ):
        raise ValueError("Invalid evidence comparison manifest")
    try:
        AgentBudget(**manifest["budget"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid evidence comparison budget") from exc
    for label, identity in (
        ("policy", "policy_id"),
        ("corpus", "corpus_id"),
    ):
        binding = manifest[f"knowledge_{label}"]
        if (
            not isinstance(binding, dict)
            or set(binding) != {"path", "sha256", identity}
            or not isinstance(binding["path"], str)
            or not binding["path"]
            or any(
                not isinstance(binding[name], str)
                or not _SHA256.fullmatch(binding[name])
                for name in ("sha256", identity)
            )
        ):
            raise ValueError("Invalid evidence comparison knowledge binding")
    cases = manifest["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evidence comparison manifest requires cases")
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
                "plan",
                "reference_answer",
                "criteria",
            }
            or not isinstance(case["case_id"], str)
            or not _CASE_ID.fullmatch(case["case_id"])
            or case["case_id"] in seen
            or not isinstance(case["category"], str)
            or not case["category"]
            or not isinstance(case["report"], str)
            or not case["report"]
            or any(
                not isinstance(case[name], str) or not _SHA256.fullmatch(case[name])
                for name in ("report_sha256", "bundle_sha256")
            )
            or not isinstance(case["reference_answer"], str)
            or not case["reference_answer"]
        ):
            raise ValueError("Invalid evidence comparison case")
        seen.add(case["case_id"])
        verify_agent_evidence_plan(case["plan"])
        _criteria(case["criteria"])
    return {
        "status": "passed",
        "manifest_id": manifest["manifest_id"],
        "cases": len(cases),
        "reference_kind": "agent-authored-pre-inference",
    }


def load_agent_evidence_comparison_manifest(path: Path) -> dict[str, Any]:
    manifest = read(path)
    verify_agent_evidence_comparison_manifest(manifest)
    return manifest


def _score_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    verification = verify_agent_evidence_plan_result(case["plan"], result)
    trace = result["trace"]
    tools = [
        event["tool_name"] for event in trace["events"] if event["kind"] == "tool"
    ]
    expected_tools = [step["tool_name"] for step in case["plan"]["steps"]]
    model_identity = trace["model"]
    checks = {
        "status": result["status"] == "passed",
        "planned_tools": tools == expected_tools,
        "complete_citations": verification["cited_observations"]
        == len(expected_tools),
        "single_model_call": trace["usage"]["model_calls"] == 1,
    }
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "structural_status": "passed" if all(checks.values()) else "failed",
        "plan_id": case["plan"]["plan_id"],
        "result_id": result["result_id"],
        "model": copy.deepcopy(model_identity),
        "tool_sequence": tools,
        "checks": checks,
        "usage": copy.deepcopy(trace["usage"]),
        "target_answer": trace["final"]["summary"] if trace["final"] else None,
        "reference_answer": case["reference_answer"],
        "criteria": copy.deepcopy(case["criteria"]),
        "semantic_comparison": "pending",
    }


def _result_body(
    manifest: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    structural_status = (
        "passed"
        if all(row["structural_status"] == "passed" for row in rows)
        else "failed"
    )
    body = {
        "artifact_type": "agent-evidence-comparison-result",
        "schema_version": RESULT_VERSION,
        "status": structural_status,
        "comparison_id": manifest["comparison_id"],
        "manifest_id": manifest["manifest_id"],
        "model": copy.deepcopy(manifest["model"]),
        "reference_author": manifest["reference_author"],
        "reference_boundary": manifest["reference_boundary"],
        "semantic_status": "pending_comparative_review",
        "summary": {
            "case_count": len(rows),
            "structurally_passed": sum(
                row["structural_status"] == "passed" for row in rows
            ),
            "structurally_failed": sum(
                row["structural_status"] == "failed" for row in rows
            ),
            "pending_semantic_comparisons": len(rows),
            "model_calls": sum(row["usage"]["model_calls"] for row in rows),
            "tool_calls": sum(row["usage"]["tool_calls"] for row in rows),
            "total_tokens": sum(row["usage"]["total_tokens"] for row in rows),
        },
        "cases": rows,
        "boundary": RESULT_BOUNDARY,
    }
    return {"result_id": digest(body), **body}


def _verify_frozen_inputs(
    root: Path, implementation_root: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, Any]]:
    if manifest["implementation_sha256"] != comparison_implementation_digest(
        implementation_root
    ):
        raise ValueError("Evidence comparison implementation changed after freezing")
    for label, identity in (
        ("policy", "policy_id"),
        ("corpus", "corpus_id"),
    ):
        binding = manifest[f"knowledge_{label}"]
        path = _resolve(root, binding["path"], f"Knowledge {label}")
        value = read(path)
        if _sha256(path) != binding["sha256"] or value.get(identity) != binding[identity]:
            raise ValueError(f"Frozen knowledge {label} changed")
    policy_path = _resolve(
        root, manifest["knowledge_policy"]["path"], "Knowledge policy"
    )
    policy = load_agent_knowledge_policy(policy_path)
    reports: dict[str, Path] = {}
    for case in manifest["cases"]:
        report = _resolve(root, case["report"], "Evidence comparison report")
        if (
            _sha256(report) != case["report_sha256"]
            or _bundle_digest(report) != case["bundle_sha256"]
        ):
            raise ValueError("Frozen comparison evidence changed: " + case["case_id"])
        reports[case["case_id"]] = report
    return reports, policy


def run_agent_evidence_comparison(
    root: Path,
    implementation_root: Path,
    manifest_path: Path,
    expected_manifest_id: str,
    output: Path,
    *,
    client: ModelClient,
    knowledge_endpoint: ServiceEndpoint,
) -> dict[str, Any]:
    manifest = load_agent_evidence_comparison_manifest(manifest_path)
    if manifest["manifest_id"] != expected_manifest_id:
        raise ValueError("Evidence comparison manifest ID differs from frozen ID")
    if output.exists() or output.is_symlink():
        raise ValueError("Evidence comparison output must be absent")
    reports, policy = _verify_frozen_inputs(root, implementation_root, manifest)
    output.mkdir(parents=True)
    results_dir = output / "results"
    results_dir.mkdir()
    budget = AgentBudget(**manifest["budget"])
    rows: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        registry = build_readonly_registry(
            reports[case["case_id"]],
            knowledge_endpoint=knowledge_endpoint,
            knowledge_policy=policy,
        )
        result = run_agent_evidence_plan(
            case["plan"], registry, client, manifest["model"]["name"], budget
        )
        identity = result["trace"]["model"]
        if identity is not None and (
            identity.get("name") != manifest["model"]["name"]
            or identity.get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Evidence comparison model differs from frozen identity")
        save_agent_evidence_plan_result(
            case["plan"], result, results_dir / f"{case['case_id']}.json"
        )
        row = _score_case(case, result)
        row["result"] = f"results/{case['case_id']}.json"
        rows.append(row)
        (output / "partial.json").write_text(
            canonical(
                {
                    "complete": False,
                    "comparison_id": manifest["comparison_id"],
                    "manifest_id": manifest["manifest_id"],
                    "cases": rows,
                }
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    result = _result_body(manifest, rows)
    (output / "comparison.json").write_text(
        canonical(result) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def verify_agent_evidence_comparison(
    manifest_path: Path, directory: Path
) -> dict[str, Any]:
    manifest = load_agent_evidence_comparison_manifest(manifest_path)
    result = read(directory / "comparison.json")
    fields = {
        "result_id",
        "artifact_type",
        "schema_version",
        "status",
        "comparison_id",
        "manifest_id",
        "model",
        "reference_author",
        "reference_boundary",
        "semantic_status",
        "summary",
        "cases",
        "boundary",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result["artifact_type"] != "agent-evidence-comparison-result"
        or result["schema_version"] != RESULT_VERSION
        or result["boundary"] != RESULT_BOUNDARY
        or result["comparison_id"] != manifest["comparison_id"]
        or result["manifest_id"] != manifest["manifest_id"]
        or canonical(result["model"]) != canonical(manifest["model"])
        or result["reference_author"] != manifest["reference_author"]
        or result["reference_boundary"] != manifest["reference_boundary"]
        or result["semantic_status"] != "pending_comparative_review"
        or result["result_id"]
        != digest({name: result[name] for name in result if name != "result_id"})
        or not isinstance(result["cases"], list)
        or len(result["cases"]) != len(manifest["cases"])
    ):
        raise ValueError("Invalid evidence comparison result metadata")
    rows: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        if not isinstance(recorded, dict) or recorded.get("case_id") != case["case_id"]:
            raise ValueError("Evidence comparison result case order differs")
        relative = recorded.get("result")
        if not isinstance(relative, str):
            raise ValueError("Evidence comparison case result path is invalid")
        saved = read(_resolve(directory, relative, "Evidence comparison case result"))
        identity = saved["trace"]["model"]
        if identity is not None and (
            identity.get("name") != manifest["model"]["name"]
            or identity.get("digest") != manifest["model"]["digest"]
        ):
            raise ValueError("Evidence comparison result model changed")
        row = _score_case(case, saved)
        row["result"] = relative
        rows.append(row)
        if canonical(row) != canonical(recorded):
            raise ValueError("Evidence comparison row differs from saved evidence")
    expected = _result_body(manifest, rows)
    if canonical(expected) != canonical(result):
        raise ValueError("Evidence comparison summary differs from saved evidence")
    return {
        "status": "passed",
        "comparison_status": result["status"],
        "semantic_status": result["semantic_status"],
        "result_id": result["result_id"],
        "manifest_id": manifest["manifest_id"],
        "cases": len(rows),
    }
