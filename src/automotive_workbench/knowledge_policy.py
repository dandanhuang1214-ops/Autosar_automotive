"""Versioned, fail-closed knowledge trust policy for future Agent tools."""
from __future__ import annotations

import copy
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from automotive_workbench.project_explanation import digest

POLICY_VERSION = "knowledge-source-policy-0.1"
AGENT_PROFILE = "agent-read"
AGENT_AUTHORITIES = frozenset({"official", "user_reviewed"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def policy_body(policy: dict[str, Any]) -> dict[str, Any]:
    """Return the content covered by policy_id."""
    return {
        "schema_version": policy.get("schema_version"),
        "profile": policy.get("profile"),
        "documents": policy.get("documents"),
    }


def validate_agent_knowledge_policy(value: Any) -> dict[str, Any]:
    """Validate an explicit Agent allowlist and its human review records."""
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "policy_id", "profile", "documents"
    }:
        raise ValueError("Invalid Agent knowledge policy fields")
    if value["schema_version"] != POLICY_VERSION or value["profile"] != AGENT_PROFILE:
        raise ValueError("Unsupported Agent knowledge policy version or profile")
    if not isinstance(value["documents"], list) or not value["documents"]:
        raise ValueError("Agent knowledge policy requires an explicit document allowlist")

    seen: set[int] = set()
    for entry in value["documents"]:
        if not isinstance(entry, dict) or set(entry) != {
            "document_id", "document_sha256", "authority", "review"
        }:
            raise ValueError("Invalid Agent knowledge policy document entry")
        document_id = entry["document_id"]
        if type(document_id) is not int or document_id < 1 or document_id in seen:
            raise ValueError("Agent knowledge policy document IDs must be unique positive integers")
        seen.add(document_id)
        if not isinstance(entry["document_sha256"], str) or not _SHA256.fullmatch(
            entry["document_sha256"]
        ):
            raise ValueError("Invalid Agent knowledge policy document digest")
        if entry["authority"] not in AGENT_AUTHORITIES:
            raise ValueError("Agent knowledge policy forbids this authority")
        review = entry["review"]
        if not isinstance(review, dict) or set(review) != {
            "decision", "reviewer", "reviewed_at"
        }:
            raise ValueError("Invalid Agent knowledge policy review record")
        if review["decision"] != "approved":
            raise ValueError("Agent knowledge policy review must be approved")
        if not isinstance(review["reviewer"], str) or not review["reviewer"].strip():
            raise ValueError("Agent knowledge policy review requires a reviewer")
        if not isinstance(review["reviewed_at"], str):
            raise ValueError("Agent knowledge policy review requires a timestamp")
        try:
            reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid Agent knowledge policy review timestamp") from exc
        if reviewed_at.tzinfo is None:
            raise ValueError("Agent knowledge policy review timestamp requires a timezone")

    if not isinstance(value["policy_id"], str) or not _SHA256.fullmatch(value["policy_id"]):
        raise ValueError("Invalid Agent knowledge policy ID")
    if value["policy_id"] != digest(policy_body(value)):
        raise ValueError("Agent knowledge policy ID does not bind policy content")
    return copy.deepcopy(value)


def load_agent_knowledge_policy(path: Path) -> dict[str, Any]:
    """Load a checked policy without accepting duplicate JSON fields."""
    def pairs(items):
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate Agent knowledge policy field")
            result[key] = item
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    return validate_agent_knowledge_policy(value)


def authorize_agent_document(
    document: Any, policy: dict[str, Any]
) -> dict[str, Any]:
    """Bind a live registry row to one explicitly reviewed policy entry."""
    checked = validate_agent_knowledge_policy(policy)
    if not isinstance(document, dict) or type(document.get("id")) is not int:
        raise ValueError("Invalid knowledge document registry row")
    if document.get("authority") == "legacy_trusted":
        raise ValueError("legacy_trusted is migration-only and forbidden for Agent tools")
    matches = [
        entry for entry in checked["documents"]
        if entry["document_id"] == document["id"]
    ]
    if len(matches) != 1:
        raise ValueError("Knowledge document is not in the Agent allowlist")
    entry = matches[0]
    if (
        document.get("enabled") is not True
        or document.get("status") != "ready"
        or document.get("review_status") != "approved"
        or document.get("authority") != entry["authority"]
        or document.get("sha256") != entry["document_sha256"]
    ):
        raise ValueError("Knowledge document differs from the reviewed Agent policy")
    return copy.deepcopy(entry)
