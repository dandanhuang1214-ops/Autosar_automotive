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


if __name__ == "__main__":
    unittest.main()
