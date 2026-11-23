"""Read-only evidence for portable project-acceptance-0.3 reports."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from automotive_workbench.evidence_bundle import verify_evidence_bundle
from automotive_workbench.project_declared import validate_declared_sources
from automotive_workbench.project_explanation import BOUNDARY, POLICY, digest, read
from automotive_workbench.project_review import load_project_report, run_project_review

REPORT_VERSION = "project-acceptance-0.3"


def verify_declared_report(report: Path) -> dict[str, Any]:
    raw = report.read_bytes()
    document = load_project_report(report)
    bundle = report.parent
    delivery = bundle.parent
    if (document["schema_version"] != REPORT_VERSION
            or report.name != "project-report.json" or bundle.name != "bundle"):
        raise ValueError("Declared communication report requires the portable 0.3 bundle layout")
    with tempfile.TemporaryDirectory(prefix="workbench-project-evidence-") as temporary:
        verified = verify_evidence_bundle(
            bundle, delivery / "manifest.json", Path(temporary), base=delivery,
        )
    if verified["status"] != "passed":
        raise ValueError("Declared communication evidence bundle failed verification")
    validate_declared_sources(report, document)
    if report.read_bytes() != raw:
        raise ValueError("Declared communication report changed during verification")
    return {
        "status": "passed",
        "project_status": document["status"],
        "report_sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_declared_request(report: Path, question: str) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Question must contain 1..4000 characters")
    verification = verify_declared_report(report)
    with tempfile.TemporaryDirectory(prefix="workbench-declared-review-") as temporary:
        directory = Path(temporary) / "review"
        review = run_project_review(report, directory)
        if review["status"] != "answered" or review["citation_validation"]["status"] != "passed":
            raise ValueError("Project facts require fully validated review citations")
        request = read(directory / "review-request.json")
    assertions = {check["check_id"]: check["assertion"]["expected"] for check in request["checks"]}
    facts = []
    for citation in review["citations"]:
        fact = {
            "source_kind": "project",
            "artifact_id": citation["artifact_id"],
            "source_sha256": citation["source_sha256"],
            "pointer": citation["locator"]["pointer"],
            "value": assertions[citation["supports_checks"][0]],
        }
        facts.append({"fact_id": digest(fact), **fact})
    if verify_declared_report(report) != verification:
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
