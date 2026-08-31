from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.review import (
    load_review_request,
    run_review,
    validate_citations,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "examples" / "review"
REQUEST = SAMPLE_DIR / "review_request.json"
EVIDENCE = SAMPLE_DIR / "engineering_evidence.sample.json"


class ReviewTests(unittest.TestCase):
    def _write_fixture(
        self,
        root: Path,
        request: dict | None = None,
        evidence: dict | None = None,
    ) -> Path:
        request_payload = request or json.loads(REQUEST.read_text(encoding="utf-8"))
        evidence_payload = evidence or json.loads(EVIDENCE.read_text(encoding="utf-8"))
        (root / "engineering_evidence.sample.json").write_text(
            json.dumps(evidence_payload), encoding="utf-8"
        )
        request_path = root / "review_request.json"
        request_path.write_text(json.dumps(request_payload), encoding="utf-8")
        return request_path

    def test_runs_answered_review_with_valid_json_pointer_citations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review(REQUEST, output)
            persisted = json.loads(
                (output / "review-result.json").read_text(encoding="utf-8")
            )
            evidence_units = json.loads(
                (output / "evidence-units.json").read_text(encoding="utf-8")
            )
            markdown = (output / "review-result.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["mode"], "retrieval-only")
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(len(result["citations"]), 4)
        self.assertEqual(result["citation_validation"]["status"], "passed")
        self.assertEqual(len(evidence_units), result["evidence_unit_count"])
        self.assertNotIn("_search_tokens", evidence_units[0])
        self.assertEqual(
            {item["locator"]["pointer"] for item in result["citations"]},
            {
                "/findings/0/code",
                "/findings/0/message",
                "/repair_summary/copies_agree",
                "/repair_summary/outcome",
            },
        )
        expected_finding = json.loads(EVIDENCE.read_text(encoding="utf-8"))["findings"][0]
        self.assertEqual(result["findings"], [expected_finding])
        self.assertEqual(persisted["schema_version"], "review-result-0.1")
        self.assertIn("retrieval-only", markdown)

    def test_reports_partial_when_one_required_check_is_unsupported(self) -> None:
        request = json.loads(REQUEST.read_text(encoding="utf-8"))
        request["checks"].append({
            "check_id": "unsupported-hardware-proof",
            "statement": "The evidence proves physical flash atomicity.",
            "terms": ["physical flash atomicity certification"],
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = self._write_fixture(root, request=request)

            result = run_review(request_path, root / "output")

        self.assertEqual(result["status"], "partial")
        self.assertAlmostEqual(result["coverage"], 2 / 3)
        self.assertEqual(result["checks"][-1]["status"], "unsupported")
        self.assertEqual(
            result["refusal_reasons"][0]["code"],
            "REVIEW-COVERAGE-BELOW-THRESHOLD",
        )

    def test_refuses_missing_denied_stale_and_zero_evidence(self) -> None:
        base = json.loads(REQUEST.read_text(encoding="utf-8"))
        cases = []

        missing = copy.deepcopy(base)
        missing["artifact_registry"][0]["source"] = "missing.json"
        cases.append((missing, "REVIEW-ARTIFACT-MISSING"))

        denied = copy.deepcopy(base)
        denied["artifact_registry"][0]["confidentiality"] = "private-local"
        cases.append((denied, "REVIEW-CONFIDENTIALITY-DENIED"))

        stale = copy.deepcopy(base)
        stale["artifact_registry"][0]["expected_sha256"] = "0" * 64
        cases.append((stale, "REVIEW-ARTIFACT-HASH-MISMATCH"))

        no_evidence = copy.deepcopy(base)
        no_evidence["checks"] = [{
            "check_id": "not-present",
            "statement": "No scoped evidence contains this claim.",
            "terms": ["unfindabletoken987654321"],
        }]
        cases.append((no_evidence, "REVIEW-NO-EVIDENCE"))

        for request, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    request_path = self._write_fixture(root, request=request)

                    result = run_review(request_path, root / "output")

                self.assertEqual(result["status"], "refused")
                self.assertIn(
                    expected_code,
                    {item["code"] for item in result["refusal_reasons"]},
                )

    def test_citation_validation_fails_after_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = self._write_fixture(root)
            result = run_review(request_path, root / "output")
            mutated = json.loads(
                (root / "engineering_evidence.sample.json").read_text(encoding="utf-8")
            )
            mutated["repair_summary"]["outcome"] = "changed-after-review"
            (root / "engineering_evidence.sample.json").write_text(
                json.dumps(mutated), encoding="utf-8"
            )

            validation = validate_citations(request_path, result)

        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["valid_count"], 0)
        self.assertTrue(
            all(item["code"] == "REVIEW-CITATION-INVALID" for item in validation["reasons"])
        )

    def test_citation_validation_rejects_tampered_citation_metadata(self) -> None:
        mutations = {
            "source": "other.json",
            "content": "tampered display content",
            "evidence_id": "evidence-tampered",
            "citation_id": "citation-tampered",
            "relation": "contradicts",
        }
        for field, value in mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                request_path = self._write_fixture(root)
                result = run_review(request_path, root / "output")
                result["citations"][0][field] = value

                validation = validate_citations(request_path, result)

                self.assertEqual(validation["status"], "failed")
                self.assertEqual(validation["valid_count"], 3)
                self.assertEqual(validation["reasons"][0]["code"], "REVIEW-CITATION-INVALID")

    def test_rejects_invalid_request_contract(self) -> None:
        request = json.loads(REQUEST.read_text(encoding="utf-8"))
        request["checks"][0]["terms"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "requires non-empty terms"):
                load_review_request(path)

    def test_reviews_markdown_with_validated_one_based_line_range(self) -> None:
        request = {
            "schema_version": "review-request-0.1",
            "request_id": "markdown-review",
            "question": "What does the release note report?",
            "minimum_coverage": 1.0,
            "allowed_confidentiality": ["public"],
            "artifact_registry": [{
                "artifact_id": "release-note",
                "artifact_type": "release-note",
                "source": "release.md",
                "confidentiality": "public",
            }],
            "artifact_ids": ["release-note"],
            "checks": [{
                "check_id": "repair-result",
                "statement": "Repair committed successfully.",
                "terms": ["repair committed successfully"],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release.md").write_bytes(
                b"# Release\r\n\r\nRepair committed successfully.\r\n"
            )
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            result = run_review(request_path, root / "output")

            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["citations"][0]["locator"], {
                "type": "line-range",
                "start_line": 3,
                "end_line": 3,
            })
            self.assertEqual(result["citation_validation"]["status"], "passed")

            (root / "release.md").write_text(
                "# Release\n\nRepair failed.\n", encoding="utf-8"
            )
            self.assertEqual(
                validate_citations(request_path, result)["status"], "failed"
            )

    def test_explicit_assertion_distinguishes_agreement_and_conflict(self) -> None:
        request = {
            "schema_version": "review-request-0.2",
            "request_id": "multi-artifact-review",
            "question": "Do the reports agree on repair outcome?",
            "minimum_coverage": 1.0,
            "allowed_confidentiality": ["public"],
            "artifact_registry": [
                {
                    "artifact_id": artifact_id,
                    "artifact_type": "repair-report",
                    "source": f"{artifact_id}.json",
                    "confidentiality": "public",
                }
                for artifact_id in ("report-a", "report-b")
            ],
            "artifact_ids": ["report-a", "report-b"],
            "checks": [{
                "check_id": "repair-outcome",
                "statement": "Both reports say repair committed.",
                "terms": ["repair outcome committed"],
                "assertion": {
                    "claim_key": "repair.outcome",
                    "operator": "equals",
                    "expected": "committed",
                    "observations": [
                        {
                            "artifact_id": artifact_id,
                            "locator": {
                                "type": "json-pointer",
                                "pointer": "/repair/outcome",
                            },
                        }
                        for artifact_id in ("report-a", "report-b")
                    ],
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report-a.json").write_text(
                json.dumps({"repair": {"outcome": "committed"}}), encoding="utf-8"
            )
            (root / "report-b.json").write_text(
                json.dumps({"repair": {"outcome": "committed"}}), encoding="utf-8"
            )
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            agreed = run_review(request_path, root / "agreed")
            self.assertEqual(agreed["status"], "answered")
            self.assertEqual(agreed["checks"][0]["status"], "supported")
            self.assertEqual(
                {item["relation"] for item in agreed["citations"]}, {"supports"}
            )

            (root / "report-b.json").write_text(
                json.dumps({"repair": {"outcome": "failed"}}), encoding="utf-8"
            )
            conflicted = run_review(request_path, root / "conflicted")
            request["checks"][0]["assertion"]["operator"] = "all-equal"
            request["checks"][0]["assertion"].pop("expected")
            request_path.write_text(json.dumps(request), encoding="utf-8")
            all_equal_conflict = run_review(request_path, root / "all-equal-conflict")

        self.assertEqual(conflicted["schema_version"], "review-result-0.2")
        self.assertEqual(conflicted["status"], "refused")
        self.assertEqual(conflicted["checks"][0]["status"], "conflicted")
        self.assertEqual(
            {item["relation"] for item in conflicted["citations"]},
            {"supports", "contradicts"},
        )
        self.assertIn(
            "REVIEW-EVIDENCE-CONFLICT",
            {item["code"] for item in conflicted["refusal_reasons"]},
        )
        self.assertEqual(conflicted["citation_validation"]["status"], "passed")
        self.assertEqual(all_equal_conflict["status"], "refused")
        self.assertEqual(all_equal_conflict["checks"][0]["status"], "conflicted")
        self.assertEqual(all_equal_conflict["citation_validation"]["status"], "passed")

    def test_similar_artifacts_without_assertion_do_not_create_conflict(self) -> None:
        request = {
            "schema_version": "review-request-0.2",
            "request_id": "non-comparable-review",
            "question": "Is repair outcome mentioned?",
            "minimum_coverage": 1.0,
            "allowed_confidentiality": ["public"],
            "artifact_registry": [
                {
                    "artifact_id": artifact_id,
                    "artifact_type": "repair-report",
                    "source": f"{artifact_id}.json",
                    "confidentiality": "public",
                }
                for artifact_id in ("variant-a", "variant-b")
            ],
            "artifact_ids": ["variant-a", "variant-b"],
            "checks": [{
                "check_id": "repair-mentioned",
                "statement": "A scoped report mentions repair outcome.",
                "terms": ["repair outcome"],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for artifact_id, outcome in (("variant-a", "committed"), ("variant-b", "failed")):
                (root / f"{artifact_id}.json").write_text(
                    json.dumps({"repair": {"outcome": outcome}}), encoding="utf-8"
                )
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            result = run_review(request_path, root / "output")

        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["checks"][0]["status"], "supported")
        self.assertNotIn(
            "REVIEW-EVIDENCE-CONFLICT",
            {item["code"] for item in result["refusal_reasons"]},
        )

    def test_invalid_assertion_line_range_blocks_review(self) -> None:
        request = {
            "schema_version": "review-request-0.2",
            "request_id": "invalid-range-review",
            "question": "What does the note say?",
            "minimum_coverage": 1.0,
            "allowed_confidentiality": ["public"],
            "artifact_registry": [{
                "artifact_id": "note",
                "artifact_type": "release-note",
                "source": "note.md",
                "confidentiality": "public",
            }],
            "artifact_ids": ["note"],
            "checks": [{
                "check_id": "note-state",
                "statement": "The note says committed.",
                "terms": ["committed"],
                "assertion": {
                    "claim_key": "note.state",
                    "operator": "equals",
                    "expected": "committed",
                    "observations": [{
                        "artifact_id": "note",
                        "locator": {
                            "type": "line-range",
                            "start_line": 3,
                            "end_line": 3,
                        },
                    }],
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.md").write_text("committed\n", encoding="utf-8")
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            result = run_review(request_path, root / "output")

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["checks"][0]["status"], "blocked")
        self.assertIn(
            "REVIEW-OBSERVATION-INVALID",
            {item["code"] for item in result["refusal_reasons"]},
        )


if __name__ == "__main__":
    unittest.main()
