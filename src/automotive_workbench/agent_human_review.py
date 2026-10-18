"""Build and verify blind human-review artifacts from read-only Agent evaluations."""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
from pathlib import Path
import re
from typing import Any

from automotive_workbench.agent_evaluation import (
    load_agent_evaluation_manifest,
    verify_agent_evaluation,
)
from automotive_workbench.agent_runtime import verify_agent_trace
from automotive_workbench.project_explanation import canonical, digest, read

PACK_VERSION = "agent-human-review-pack-0.1"
TEMPLATE_VERSION = "agent-human-review-template-0.1"
ASSESSMENT_VERSION = "agent-human-review-assessment-0.1"
PACK_BOUNDARY = (
    "The pack intentionally omits frozen gold, categories, automated case scores, and "
    "developer conclusions. It exposes the original question, unassessed model answer, "
    "and cited immutable observations so a reviewer can form an independent judgment."
)
ASSESSMENT_BOUNDARY = (
    "This artifact records a human review; Workbench verifies completeness, identity, "
    "and hashes only. It does not infer that any judgment is correct."
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMPLEMENTATION_FILES = (
    "src/automotive_workbench/agent_human_review.py",
    "src/automotive_workbench/agent_evaluation.py",
    "src/automotive_workbench/agent_runtime.py",
)
_JUDGMENTS = {"pass", "fail", "not_assessable"}
_APPLICABILITY = {"applicable", "not_applicable", "uncertain", "not_assessable"}
_USABILITY = {"direct", "needs_edits", "not_usable", "not_assessable"}


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
        raise ValueError(f"{label} escapes its root")
    return path


def review_implementation_digest(root: Path) -> str:
    files: dict[str, str] = {}
    for relative in _IMPLEMENTATION_FILES:
        path = _resolve(root, relative, "Agent human-review implementation")
        files[relative] = _sha256(path)
    return digest(files)


def _review_evidence(trace: dict[str, Any]) -> list[dict[str, Any]]:
    cited = set(trace["final"]["evidence_ids"]) if trace["final"] else set()
    observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in trace["events"]:
        if (
            event.get("kind") != "tool"
            or event.get("status") != "passed"
            or event.get("observation_id") not in cited
        ):
            continue
        observation_id = event["observation_id"]
        if observation_id in seen:
            raise ValueError("Agent human-review evidence contains a duplicate observation")
        seen.add(observation_id)
        observations.append(
            {
                "observation_id": observation_id,
                "tool_name": event["tool_name"],
                "arguments": copy.deepcopy(event["arguments"]),
                "result_sha256": event["result_sha256"],
                "result": copy.deepcopy(event["result"]),
            }
        )
    if trace["final"] is not None and seen != cited:
        raise ValueError("Agent human-review pack cannot resolve all cited observations")
    return observations


def _pack_body(
    implementation_root: Path,
    manifest_path: Path,
    evaluation_directory: Path,
) -> dict[str, Any]:
    verification = verify_agent_evaluation(manifest_path, evaluation_directory)
    manifest = load_agent_evaluation_manifest(manifest_path)
    result = read(evaluation_directory / "evaluation.json")
    if result.get("result_id") != verification["result_id"]:
        raise ValueError("Agent human-review source result differs from offline verification")
    items: list[dict[str, Any]] = []
    for case, recorded in zip(manifest["cases"], result["cases"], strict=True):
        relative = recorded.get("trace")
        if not isinstance(relative, str):
            raise ValueError("Agent human-review source trace path is invalid")
        trace = read(_resolve(evaluation_directory, relative, "Agent human-review trace"))
        verify_agent_trace(trace)
        if trace.get("trace_id") != recorded.get("trace_id"):
            raise ValueError("Agent human-review source trace identity differs")
        review_item_id = digest(
            {"manifest_id": manifest["manifest_id"], "case_id": case["case_id"]}
        )
        items.append(
            {
                "review_item_id": review_item_id,
                "question": case["goal"],
                "agent_status": trace["status"],
                "agent_reason": trace["reason"],
                "answer": trace["final"]["summary"] if trace["final"] else None,
                "semantic_status": "unassessed",
                "cited_evidence": _review_evidence(trace),
                "trace_id": trace["trace_id"],
            }
        )
    return {
        "artifact_type": "agent-human-review-pack",
        "schema_version": PACK_VERSION,
        "producer_sha256": review_implementation_digest(implementation_root),
        "manifest_id": manifest["manifest_id"],
        "result_id": result["result_id"],
        "evaluation_id": manifest["evaluation_id"],
        "model": copy.deepcopy(manifest["model"]),
        "items": items,
        "boundary": PACK_BOUNDARY,
    }


def _template_body(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "agent-human-review-template",
        "schema_version": TEMPLATE_VERSION,
        "review_pack_id": pack["review_pack_id"],
        "status": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "items": [
            {
                "review_item_id": item["review_item_id"],
                "independent_expected_answer": None,
                "answer_coverage": None,
                "causal_support": None,
                "boundary_fidelity": None,
                "knowledge_applicability": None,
                "recommendation_boundary": None,
                "usability": None,
                "required_edits": None,
                "notes": None,
            }
            for item in pack["items"]
        ],
    }


def _markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# Independent Agent explanation review",
        "",
        f"Review pack: `{pack['review_pack_id']}`",
        "",
        "Write the expected answer before judging the model answer. Frozen gold and "
        "automated case scores are intentionally absent.",
    ]
    for index, item in enumerate(pack["items"], 1):
        lines.extend(
            [
                "",
                f"## Review item {index}",
                "",
                f"ID: `{item['review_item_id']}`",
                "",
                "Question:",
                "",
                item["question"],
                "",
                "Independent expected answer (complete before reading the answer):",
                "",
                "<!-- reviewer fills this -->",
                "",
                f"Cited observations: {len(item['cited_evidence'])}",
                "",
                "```json",
                canonical(item["cited_evidence"]),
                "```",
                "",
                "Model answer:",
                "",
                item["answer"] if item["answer"] is not None else "[no answer]",
                "",
                "Record coverage, causal support, boundary fidelity, knowledge "
                "applicability, recommendation boundary, usability, and required edits "
                "in `review-template.json`.",
            ]
        )
    return "\n".join(lines) + "\n"


def prepare_agent_human_review(
    implementation_root: Path,
    manifest_path: Path,
    evaluation_directory: Path,
    output: Path,
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent human-review output must be absent")
    body = _pack_body(implementation_root, manifest_path, evaluation_directory)
    pack = {"review_pack_id": digest(body), **body}
    template_body = _template_body(pack)
    template = {"template_id": digest(template_body), **template_body}
    output.mkdir(parents=True)
    (output / "review-pack.json").write_text(
        canonical(pack) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "review-template.json").write_text(
        canonical(template) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "review-pack.md").write_text(
        _markdown(pack), encoding="utf-8", newline="\n"
    )
    return pack


def load_agent_human_review_pack(path: Path) -> dict[str, Any]:
    pack = read(path)
    fields = {
        "review_pack_id", "artifact_type", "schema_version", "producer_sha256",
        "manifest_id", "result_id", "evaluation_id", "model", "items", "boundary",
    }
    if (
        not isinstance(pack, dict)
        or set(pack) != fields
        or pack["artifact_type"] != "agent-human-review-pack"
        or pack["schema_version"] != PACK_VERSION
        or pack["boundary"] != PACK_BOUNDARY
        or pack["review_pack_id"]
        != digest({name: pack[name] for name in pack if name != "review_pack_id"})
        or any(not isinstance(pack[name], str) or not _SHA256.fullmatch(pack[name])
               for name in ("producer_sha256", "manifest_id", "result_id"))
        or not isinstance(pack["evaluation_id"], str)
        or not pack["evaluation_id"]
        or not isinstance(pack["model"], dict)
        or set(pack["model"]) != {"name", "digest"}
        or not isinstance(pack["model"]["name"], str)
        or not pack["model"]["name"]
        or not isinstance(pack["model"]["digest"], str)
        or not _SHA256.fullmatch(pack["model"]["digest"])
        or not isinstance(pack["items"], list)
        or not pack["items"]
    ):
        raise ValueError("Invalid Agent human-review pack")
    seen: set[str] = set()
    for item in pack["items"]:
        required = {
            "review_item_id", "question", "agent_status", "agent_reason", "answer",
            "semantic_status", "cited_evidence", "trace_id",
        }
        if (
            not isinstance(item, dict)
            or set(item) != required
            or not isinstance(item["review_item_id"], str)
            or not _SHA256.fullmatch(item["review_item_id"])
            or item["review_item_id"] in seen
            or not isinstance(item["question"], str)
            or not item["question"]
            or item["agent_status"] not in {"passed", "refused", "blocked"}
            or not isinstance(item["agent_reason"], str)
            or not item["agent_reason"]
            or (item["answer"] is not None and not isinstance(item["answer"], str))
            or item["semantic_status"] != "unassessed"
            or not isinstance(item["cited_evidence"], list)
            or not isinstance(item["trace_id"], str)
            or not _SHA256.fullmatch(item["trace_id"])
        ):
            raise ValueError("Invalid Agent human-review item")
        seen.add(item["review_item_id"])
        evidence_seen: set[str] = set()
        for evidence in item["cited_evidence"]:
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {
                    "observation_id", "tool_name", "arguments", "result_sha256", "result"
                }
                or not isinstance(evidence["observation_id"], str)
                or not _SHA256.fullmatch(evidence["observation_id"])
                or evidence["observation_id"] in evidence_seen
                or not isinstance(evidence["tool_name"], str)
                or not evidence["tool_name"]
                or not isinstance(evidence["arguments"], dict)
                or not isinstance(evidence["result_sha256"], str)
                or not _SHA256.fullmatch(evidence["result_sha256"])
                or not isinstance(evidence["result"], dict)
                or digest(evidence["result"]) != evidence["result_sha256"]
            ):
                raise ValueError("Invalid Agent human-review evidence")
            evidence_seen.add(evidence["observation_id"])
    return pack


def verify_agent_human_review(
    implementation_root: Path,
    manifest_path: Path,
    evaluation_directory: Path,
    directory: Path,
) -> dict[str, Any]:
    pack = load_agent_human_review_pack(directory / "review-pack.json")
    expected_body = _pack_body(implementation_root, manifest_path, evaluation_directory)
    expected = {"review_pack_id": digest(expected_body), **expected_body}
    if canonical(pack) != canonical(expected):
        raise ValueError("Agent human-review pack differs from source evaluation")
    template = read(directory / "review-template.json")
    expected_template_body = _template_body(pack)
    expected_template = {
        "template_id": digest(expected_template_body), **expected_template_body
    }
    if canonical(template) != canonical(expected_template):
        raise ValueError("Agent human-review template differs from review pack")
    if (directory / "review-pack.md").read_text(encoding="utf-8") != _markdown(pack):
        raise ValueError("Agent human-review Markdown differs from review pack")
    return {
        "status": "passed",
        "review_pack_id": pack["review_pack_id"],
        "item_count": len(pack["items"]),
        "semantic_status": "pending_human_review",
    }


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Agent human review requires a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid Agent human-review timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Agent human-review timestamp requires a timezone")
    return value


def _assessment_body(pack: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "template_id", "artifact_type", "schema_version", "review_pack_id", "status",
        "reviewer", "reviewed_at", "items",
    }
    if (
        not isinstance(draft, dict)
        or set(draft) != fields
        or draft["artifact_type"] != "agent-human-review-template"
        or draft["schema_version"] != TEMPLATE_VERSION
        or draft["review_pack_id"] != pack["review_pack_id"]
        or draft["status"] != "completed"
        or not isinstance(draft["reviewer"], str)
        or not draft["reviewer"].strip()
        or not isinstance(draft["items"], list)
        or len(draft["items"]) != len(pack["items"])
    ):
        raise ValueError("Incomplete Agent human-review draft")
    template_id = draft["template_id"]
    if template_id != digest(_template_body(pack)):
        raise ValueError("Invalid Agent human-review template identity")
    reviewed_at = _timestamp(draft["reviewed_at"])
    items: list[dict[str, Any]] = []
    for source, item in zip(pack["items"], draft["items"], strict=True):
        required = {
            "review_item_id", "independent_expected_answer", "answer_coverage",
            "causal_support", "boundary_fidelity", "knowledge_applicability",
            "recommendation_boundary", "usability", "required_edits", "notes",
        }
        if (
            not isinstance(item, dict)
            or set(item) != required
            or item["review_item_id"] != source["review_item_id"]
            or not isinstance(item["independent_expected_answer"], str)
            or not item["independent_expected_answer"].strip()
            or len(item["independent_expected_answer"]) > 4000
            or item["answer_coverage"] not in _JUDGMENTS
            or item["causal_support"] not in _JUDGMENTS
            or item["boundary_fidelity"] not in _JUDGMENTS
            or item["knowledge_applicability"] not in _APPLICABILITY
            or item["recommendation_boundary"] not in _JUDGMENTS
            or item["usability"] not in _USABILITY
            or not isinstance(item["required_edits"], str)
            or not isinstance(item["notes"], str)
            or len(item["required_edits"]) > 4000
            or len(item["notes"]) > 4000
        ):
            raise ValueError("Incomplete Agent human-review item")
        items.append(copy.deepcopy(item))
    counts = {
        name: sum(item["usability"] == name for item in items)
        for name in sorted(_USABILITY)
    }
    return {
        "artifact_type": "agent-human-review-assessment",
        "schema_version": ASSESSMENT_VERSION,
        "review_pack_id": pack["review_pack_id"],
        "status": "completed",
        "reviewer": draft["reviewer"].strip(),
        "reviewed_at": reviewed_at,
        "summary": {"item_count": len(items), "usability_counts": counts},
        "items": items,
        "boundary": ASSESSMENT_BOUNDARY,
    }


def finalize_agent_human_review(
    pack_path: Path, draft_path: Path, output: Path
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Agent human-review assessment output must be absent")
    pack = load_agent_human_review_pack(pack_path)
    body = _assessment_body(pack, read(draft_path))
    assessment = {"assessment_id": digest(body), **body}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(assessment) + "\n", encoding="utf-8", newline="\n")
    return assessment


def verify_agent_human_review_assessment(
    pack_path: Path, assessment_path: Path
) -> dict[str, Any]:
    pack = load_agent_human_review_pack(pack_path)
    assessment = read(assessment_path)
    fields = {
        "assessment_id", "artifact_type", "schema_version", "review_pack_id", "status",
        "reviewer", "reviewed_at", "summary", "items", "boundary",
    }
    if (
        not isinstance(assessment, dict)
        or set(assessment) != fields
        or assessment["artifact_type"] != "agent-human-review-assessment"
        or assessment["schema_version"] != ASSESSMENT_VERSION
        or assessment["review_pack_id"] != pack["review_pack_id"]
        or assessment["boundary"] != ASSESSMENT_BOUNDARY
        or assessment["assessment_id"]
        != digest({name: assessment[name] for name in assessment if name != "assessment_id"})
    ):
        raise ValueError("Invalid Agent human-review assessment")
    draft = {
        "template_id": digest(_template_body(pack)),
        "artifact_type": "agent-human-review-template",
        "schema_version": TEMPLATE_VERSION,
        "review_pack_id": assessment["review_pack_id"],
        "status": assessment["status"],
        "reviewer": assessment["reviewer"],
        "reviewed_at": assessment["reviewed_at"],
        "items": assessment["items"],
    }
    body = _assessment_body(pack, draft)
    if canonical(body) != canonical(
        {name: assessment[name] for name in assessment if name != "assessment_id"}
    ):
        raise ValueError("Agent human-review assessment summary differs from items")
    return {
        "status": "passed",
        "assessment_id": assessment["assessment_id"],
        "review_pack_id": pack["review_pack_id"],
        "item_count": len(assessment["items"]),
    }
