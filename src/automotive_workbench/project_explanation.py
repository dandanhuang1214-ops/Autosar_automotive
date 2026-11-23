"""Read-only P30 fact selection. No model prose is certified by this gate."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from automotive_workbench.project_ecuc import verify
from automotive_workbench.project_review import run_project_review

POLICY = "project-fact-selection-0.1"
BOUNDARY = (
    "Only exact recorded project facts are accepted. No manual knowledge, causal "
    "inference, new execution, or free-form model claim is verified. Selecting "
    "facts does not establish that they answer the question."
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    canonical(value)  # Reject non-finite numbers, including inside arbitrary values.
    return value


def build_request(report: Path, question: str) -> dict[str, Any]:
    """Replay the bundle and export only already audited assertion facts."""
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Question must contain 1..4000 characters")
    if report.is_symlink() or not report.is_file():
        raise ValueError("Project report must be a regular non-symlink file")
    initial = report.read_bytes()
    verification = verify(report)  # Limited to replayable ECUC project 0.6--0.9.
    with tempfile.TemporaryDirectory(prefix="workbench-explanation-") as temporary:
        output = Path(temporary) / "review"
        reviewed = run_project_review(report, output)
        if reviewed["status"] != "answered" or reviewed["citation_validation"]["status"] != "passed":
            raise ValueError("Project facts require fully validated review citations")
        request = read(output / "review-request.json")
        registry = {a["artifact_id"]: a for a in request["artifact_registry"]}
        facts = []
        for check in request["checks"]:
            assertion = check["assertion"]
            observation = assertion["observations"][0]
            artifact_id = observation["artifact_id"]
            fact = {
                "source_kind": "project",
                "artifact_id": artifact_id,
                "source_sha256": registry[artifact_id]["expected_sha256"],
                "pointer": observation["locator"]["pointer"],
                "value": assertion["expected"],
            }
            facts.append({"fact_id": digest(fact), **fact})
    # Recheck the complete dependency closure, not merely the top-level bytes.
    if verify(report) != verification or report.read_bytes() != initial:
        raise ValueError("Project evidence changed during fact extraction")
    body = {
        "schema_version": "project-explanation-request-0.1",
        "policy_version": POLICY,
        "report_sha256": verification["report_sha256"],
        "project_status": verification["project_status"],
        "question": question.strip(),
        "facts": facts,
        "boundary": BOUNDARY,
    }
    return {"request_id": digest(body), **body}


def prepare(report: Path, question: str, output: Path) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Explanation request output must be absent")
    request = build_request(report, question)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    return {"status": "passed", "request_id": request["request_id"],
            "fact_count": len(request["facts"]), "request": str(output)}


def validate_answer(report: Path, request_path: Path, answer_path: Path) -> dict[str, Any]:
    """Rebuild trusted facts; never repair a citation or accept unchecked prose."""
    saved = read(request_path)
    request = build_request(report, saved.get("question", ""))
    if canonical(saved) != canonical(request):
        raise ValueError("Explanation request differs from replayed project evidence")
    answer = read(answer_path)
    if set(answer) != {"schema_version", "request_id", "status", "claims"}:
        raise ValueError("Answer fields must match the closed fact-selection contract")
    if answer["schema_version"] != "project-explanation-answer-0.1":
        raise ValueError("Unsupported explanation answer version")
    if answer["request_id"] != request["request_id"]:
        raise ValueError("Answer belongs to a different explanation request")
    claims = answer["claims"]
    if not isinstance(claims, list) or answer["status"] not in ("selected", "unassessed"):
        raise ValueError("Invalid answer status or claims")
    if (answer["status"] == "unassessed") != (len(claims) == 0):
        raise ValueError("Unassessed answers require no claims; selected answers require facts")
    allowed = {fact["fact_id"]: fact for fact in request["facts"]}
    selected = []
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"fact_id", "value"}:
            raise ValueError("Each claim must contain only fact_id and value")
        identity = claim["fact_id"]
        if not isinstance(identity, str) or identity not in allowed or identity in seen:
            raise ValueError("Unknown or duplicate fact citation")
        fact = allowed[identity]
        # Canonical JSON distinguishes bool/int and preserves structured values.
        if canonical(claim["value"]) != canonical(fact["value"]):
            raise ValueError("Claim value does not match cited fact")
        seen.add(identity)
        selected.append(fact)
    return {
        "status": "passed", "answer_status": answer["status"],
        "request_id": request["request_id"], "project_status": request["project_status"],
        "answer_sha256": hashlib.sha256(answer_path.read_bytes()).hexdigest(),
        "facts": selected, "boundary": BOUNDARY,
    }
