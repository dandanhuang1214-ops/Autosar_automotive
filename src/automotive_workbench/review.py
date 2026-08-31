from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_CONFIDENTIALITY = {"public", "private-local", "company-restricted"}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class _ArtifactRecord:
    artifact_id: str
    artifact_type: str
    source: str
    path: Path
    source_sha256: str
    confidentiality: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tokens(value: str) -> set[str]:
    return {item.casefold() for item in TOKEN_PATTERN.findall(value)}


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _scalar_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_finding(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(field), str)
        for field in ("code", "severity", "message", "source_artifact")
    )


def _normalize_json(
    value: Any,
    artifact: _ArtifactRecord,
    pointer: str = "",
    finding_code: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    if _is_finding(value):
        finding_code = str(value["code"])
        findings.append(copy.deepcopy(value))
    if isinstance(value, dict):
        for key in sorted(value):
            child_pointer = f"{pointer}/{_pointer_token(str(key))}"
            child_units, child_findings = _normalize_json(
                value[key], artifact, child_pointer, finding_code
            )
            units.extend(child_units)
            findings.extend(child_findings)
        return units, findings
    if isinstance(value, list):
        for index, item in enumerate(value):
            child_units, child_findings = _normalize_json(
                item, artifact, f"{pointer}/{index}", finding_code
            )
            units.extend(child_units)
            findings.extend(child_findings)
        return units, findings

    content = _scalar_content(value)
    identity = f"{artifact.artifact_id}\0{artifact.source_sha256}\0{pointer}".encode()
    units.append({
        "evidence_id": f"evidence-{_sha256(identity)[:24]}",
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "source": artifact.source,
        "source_sha256": artifact.source_sha256,
        "confidentiality": artifact.confidentiality,
        "locator": {"type": "json-pointer", "pointer": pointer},
        "content": content,
        "content_sha256": _sha256(content.encode("utf-8")),
        "finding_codes": [finding_code] if finding_code else [],
        "_search_tokens": _tokens(f"{pointer} {content}"),
    })
    return units, findings


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Review request requires non-empty {name}")
    return value


def load_review_request(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != "review-request-0.1":
        raise ValueError("Unsupported or missing review-request schema_version")
    _require_string(payload.get("request_id"), "request_id")
    _require_string(payload.get("question"), "question")
    minimum_coverage = payload.get("minimum_coverage", 1.0)
    if (
        not isinstance(minimum_coverage, (int, float))
        or isinstance(minimum_coverage, bool)
        or not 0 <= minimum_coverage <= 1
    ):
        raise ValueError("Review request minimum_coverage must be in range 0..1")

    allowed = payload.get("allowed_confidentiality")
    if not isinstance(allowed, list) or not allowed:
        raise ValueError("Review request requires non-empty allowed_confidentiality list")
    if len(set(allowed)) != len(allowed):
        raise ValueError("Review request allowed_confidentiality must be unique")
    if any(item not in SUPPORTED_CONFIDENTIALITY for item in allowed):
        raise ValueError("Review request contains unsupported confidentiality policy")

    registry = payload.get("artifact_registry")
    if not isinstance(registry, list) or not registry:
        raise ValueError("Review request requires non-empty artifact_registry list")
    registry_ids: set[str] = set()
    for index, item in enumerate(registry):
        if not isinstance(item, dict):
            raise ValueError(f"Review request artifact_registry[{index}] must be an object")
        artifact_id = _require_string(item.get("artifact_id"), "artifact_id")
        if artifact_id in registry_ids:
            raise ValueError(f"Duplicate review artifact_id: {artifact_id}")
        registry_ids.add(artifact_id)
        _require_string(item.get("artifact_type"), "artifact_type")
        _require_string(item.get("source"), "source")
        if item.get("confidentiality") not in SUPPORTED_CONFIDENTIALITY:
            raise ValueError(f"Unsupported review artifact confidentiality: {item.get('confidentiality')}")
        expected_sha256 = item.get("expected_sha256")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        ):
            raise ValueError("Review artifact expected_sha256 must be lowercase SHA-256")

    artifact_ids = payload.get("artifact_ids")
    if not isinstance(artifact_ids, list) or not artifact_ids:
        raise ValueError("Review request requires non-empty artifact_ids list")
    if len(set(artifact_ids)) != len(artifact_ids) or any(
        not isinstance(item, str) or not item for item in artifact_ids
    ):
        raise ValueError("Review request artifact_ids must be unique non-empty strings")

    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("Review request requires non-empty checks list")
    check_ids: set[str] = set()
    for index, item in enumerate(checks):
        if not isinstance(item, dict):
            raise ValueError(f"Review request checks[{index}] must be an object")
        check_id = _require_string(item.get("check_id"), "check_id")
        if check_id in check_ids:
            raise ValueError(f"Duplicate review check_id: {check_id}")
        check_ids.add(check_id)
        _require_string(item.get("statement"), "statement")
        terms = item.get("terms")
        if not isinstance(terms, list) or not terms or any(
            not isinstance(term, str) or not term for term in terms
        ):
            raise ValueError(f"Review check {check_id} requires non-empty terms")
        if not set().union(*(_tokens(term) for term in terms)):
            raise ValueError(f"Review check {check_id} terms contain no searchable tokens")
    return payload


def _reason(code: str, message: str, **context: str) -> dict[str, str]:
    return {"code": code, "message": message, **context}


def _load_artifacts(
    request_path: Path,
    request: dict[str, Any],
) -> tuple[list[_ArtifactRecord], list[dict[str, str]]]:
    registry = {item["artifact_id"]: item for item in request["artifact_registry"]}
    allowed = set(request["allowed_confidentiality"])
    records: list[_ArtifactRecord] = []
    reasons: list[dict[str, str]] = []
    for artifact_id in request["artifact_ids"]:
        item = registry.get(artifact_id)
        if item is None:
            reasons.append(_reason(
                "REVIEW-ARTIFACT-MISSING",
                f"Artifact {artifact_id} is not present in the request registry",
                artifact_id=artifact_id,
            ))
            continue
        if item["confidentiality"] not in allowed:
            reasons.append(_reason(
                "REVIEW-CONFIDENTIALITY-DENIED",
                f"Artifact {artifact_id} is outside the allowed confidentiality policy",
                artifact_id=artifact_id,
            ))
            continue
        source_path = Path(item["source"])
        if not source_path.is_absolute():
            source_path = request_path.parent / source_path
        if not source_path.is_file():
            reasons.append(_reason(
                "REVIEW-ARTIFACT-MISSING",
                f"Artifact source does not exist: {item['source']}",
                artifact_id=artifact_id,
            ))
            continue
        source_sha256 = _sha256(source_path.read_bytes())
        if item.get("expected_sha256") and item["expected_sha256"] != source_sha256:
            reasons.append(_reason(
                "REVIEW-ARTIFACT-HASH-MISMATCH",
                f"Artifact {artifact_id} does not match expected_sha256",
                artifact_id=artifact_id,
            ))
            continue
        records.append(_ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=item["artifact_type"],
            source=item["source"],
            path=source_path,
            source_sha256=source_sha256,
            confidentiality=item["confidentiality"],
        ))
    return records, reasons


def _select_supporting_units(
    units: list[dict[str, Any]], required_tokens: set[str], limit: int = 8
) -> list[dict[str, Any]]:
    candidates = [
        unit for unit in units if required_tokens & unit["_search_tokens"]
    ]
    selected: list[dict[str, Any]] = []
    uncovered = set(required_tokens)
    while candidates and uncovered and len(selected) < limit:
        candidates.sort(key=lambda unit: (
            -len(uncovered & unit["_search_tokens"]),
            unit["artifact_id"],
            unit["locator"]["pointer"],
            unit["evidence_id"],
        ))
        best = candidates.pop(0)
        if not uncovered & best["_search_tokens"]:
            break
        selected.append(best)
        uncovered -= best["_search_tokens"]
    return selected if not uncovered else []


def _public_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in unit.items() if not key.startswith("_")}


def _citation(unit: dict[str, Any], check_id: str) -> dict[str, Any]:
    identity = f"{unit['evidence_id']}\0{check_id}".encode()
    return {
        "citation_id": f"citation-{_sha256(identity)[:24]}",
        "evidence_id": unit["evidence_id"],
        "artifact_id": unit["artifact_id"],
        "source": unit["source"],
        "source_sha256": unit["source_sha256"],
        "locator": copy.deepcopy(unit["locator"]),
        "content": unit["content"],
        "content_sha256": unit["content_sha256"],
        "supports_checks": [check_id],
    }


def _resolve_json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must start with /")
    target = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(target, list):
            target = target[int(token)]
        elif isinstance(target, dict):
            target = target[token]
        else:
            raise KeyError(token)
    return target


def validate_citations(request_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    request = load_review_request(request_path)
    registry = {item["artifact_id"]: item for item in request["artifact_registry"]}
    scope = set(request["artifact_ids"])
    allowed = set(request["allowed_confidentiality"])
    check_ids = {item["check_id"] for item in request["checks"]}
    reasons: list[dict[str, str]] = []
    valid_count = 0
    for citation in result.get("citations", []):
        artifact_id = citation.get("artifact_id", "")
        item = registry.get(artifact_id)
        try:
            if artifact_id not in scope or item is None:
                raise ValueError("artifact is outside request scope")
            if item["confidentiality"] not in allowed:
                raise ValueError("artifact confidentiality is denied")
            source_path = Path(item["source"])
            if not source_path.is_absolute():
                source_path = request_path.parent / source_path
            source_bytes = source_path.read_bytes()
            source_sha256 = _sha256(source_bytes)
            if item.get("expected_sha256") not in (None, source_sha256):
                raise ValueError("source does not match expected_sha256")
            if citation.get("source") != item["source"]:
                raise ValueError("citation source does not match artifact registry")
            if source_sha256 != citation["source_sha256"]:
                raise ValueError("source hash changed")
            payload = json.loads(source_bytes.decode("utf-8-sig"))
            locator = citation["locator"]
            if locator.get("type") != "json-pointer":
                raise ValueError("unsupported locator type")
            pointer = locator["pointer"]
            content = _scalar_content(_resolve_json_pointer(payload, pointer))
            content_sha256 = _sha256(content.encode("utf-8"))
            if citation.get("content") != content:
                raise ValueError("citation display content does not match resolved content")
            if content_sha256 != citation["content_sha256"]:
                raise ValueError("resolved content hash changed")
            supports = citation.get("supports_checks")
            if not isinstance(supports, list) or not supports or not set(supports) <= check_ids:
                raise ValueError("citation references an unknown check")
            evidence_identity = (
                f"{artifact_id}\0{source_sha256}\0{pointer}".encode()
            )
            expected_evidence_id = f"evidence-{_sha256(evidence_identity)[:24]}"
            if citation.get("evidence_id") != expected_evidence_id:
                raise ValueError("evidence_id does not match resolved evidence")
            citation_identity = f"{expected_evidence_id}\0{supports[0]}".encode()
            expected_citation_id = f"citation-{_sha256(citation_identity)[:24]}"
            if len(supports) != 1 or citation.get("citation_id") != expected_citation_id:
                raise ValueError("citation_id does not match cited evidence and check")
        except (OSError, KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError) as exc:
            reasons.append(_reason(
                "REVIEW-CITATION-INVALID",
                f"Citation {citation.get('citation_id', '')} is invalid: {exc}",
                artifact_id=str(artifact_id),
            ))
        else:
            valid_count += 1
    return {
        "status": "passed" if not reasons else "failed",
        "citation_count": len(result.get("citations", [])),
        "valid_count": valid_count,
        "reasons": reasons,
    }


def render_review_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evidence-backed Engineering Review",
        "",
        f"- Request: `{result['request_id']}`",
        f"- Status: **{result['status']}**",
        f"- Mode: `{result['mode']}`",
        f"- Coverage: {result['coverage']:.3f}",
        f"- Citations: {len(result['citations'])}",
        "",
        "| Check | Status | Citations |",
        "|---|---|---:|",
    ]
    for check in result["checks"]:
        lines.append(
            f"| `{check['check_id']}` | {check['status']} | {len(check['citation_ids'])} |"
        )
    lines.extend(["", "## Refusal reasons", ""])
    if result["refusal_reasons"]:
        for reason in result["refusal_reasons"]:
            lines.append(f"- `{reason['code']}` — {reason['message']}")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This retrieval-only result is derived from explicit local JSON artifacts. It does not use an LLM, embeddings, a vector database, or implicit workspace ingestion.",
        "",
    ])
    return "\n".join(lines)


def run_review(request_path: Path, output: Path) -> dict[str, Any]:
    request = load_review_request(request_path)
    artifacts, artifact_reasons = _load_artifacts(request_path, request)
    units: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    invalid_reasons: list[dict[str, str]] = []
    for artifact in artifacts:
        try:
            payload = json.loads(artifact.path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            invalid_reasons.append(_reason(
                "REVIEW-ARTIFACT-INVALID",
                f"Artifact {artifact.artifact_id} is not valid JSON: {exc}",
                artifact_id=artifact.artifact_id,
            ))
            continue
        artifact_units, artifact_findings = _normalize_json(payload, artifact)
        units.extend(artifact_units)
        findings.extend(artifact_findings)

    blocking_reasons = [*artifact_reasons, *invalid_reasons]
    check_results: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    if blocking_reasons:
        for check in request["checks"]:
            check_results.append({
                "check_id": check["check_id"],
                "statement": check["statement"],
                "status": "blocked",
                "citation_ids": [],
            })
    else:
        for check in request["checks"]:
            required_tokens = set().union(*(_tokens(term) for term in check["terms"]))
            supporting_units = _select_supporting_units(units, required_tokens)
            check_citations = [
                _citation(unit, check["check_id"]) for unit in supporting_units
            ]
            citations.extend(check_citations)
            check_results.append({
                "check_id": check["check_id"],
                "statement": check["statement"],
                "status": "supported" if check_citations else "unsupported",
                "citation_ids": [item["citation_id"] for item in check_citations],
            })

    supported_count = sum(item["status"] == "supported" for item in check_results)
    coverage = supported_count / len(check_results)
    refusal_reasons = list(blocking_reasons)
    if blocking_reasons:
        status = "refused"
    elif supported_count == 0:
        status = "refused"
        refusal_reasons.append(_reason(
            "REVIEW-NO-EVIDENCE",
            "No required check is supported by the scoped artifacts",
        ))
    elif coverage < request.get("minimum_coverage", 1.0):
        status = "partial"
        refusal_reasons.append(_reason(
            "REVIEW-COVERAGE-BELOW-THRESHOLD",
            f"Coverage {coverage:.3f} is below {request.get('minimum_coverage', 1.0):.3f}",
        ))
    else:
        status = "answered"

    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "engineering-review-result",
        "schema_version": "review-result-0.1",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "request_id": request["request_id"],
        "question": request["question"],
        "status": status,
        "mode": "retrieval-only",
        "minimum_coverage": request.get("minimum_coverage", 1.0),
        "coverage": coverage,
        "artifact_ids": list(request["artifact_ids"]),
        "evidence_unit_count": len(units),
        "evidence_units_file": "evidence-units.json",
        "checks": check_results,
        "citations": citations,
        "findings": findings,
        "refusal_reasons": refusal_reasons,
    }
    validation = validate_citations(request_path, result)
    result["citation_validation"] = validation
    if validation["status"] == "failed":
        result["status"] = "refused"
        result["refusal_reasons"].extend(validation["reasons"])

    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence-units.json").write_text(
        json.dumps([_public_unit(unit) for unit in units], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "review-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "review-result.md").write_text(
        render_review_markdown(result), encoding="utf-8"
    )
    return result
