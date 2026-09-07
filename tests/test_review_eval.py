from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.review_eval import (
    load_evaluation_manifest,
    run_review_evaluation,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "review" / "evaluation" / "evaluation.json"
RUNTIME_MANIFEST = (
    ROOT / "examples" / "review" / "evaluation" / "runtime-evaluation.json"
)
HELD_OUT_MANIFEST = (
    ROOT / "examples" / "review" / "evaluation" / "held-out-negative.json"
)
CROSS_RUN_MANIFEST = (
    ROOT / "examples" / "review" / "evaluation" / "cross-run-evaluation.json"
)
COHORT_MANIFEST = (
    ROOT / "examples" / "review" / "evaluation" / "cohort-evaluation.json"
)
EXTERNAL_COHORT_MANIFEST = (
    ROOT / "examples" / "review" / "evaluation" / "external-cohort-evaluation.json"
)


class ReviewEvaluationTests(unittest.TestCase):
    def assert_preflight_rejection(
        self,
        output: Path,
        *,
        code: str,
        stage: str,
        field: str | None = None,
    ) -> None:
        rejection_path = output / "review-evaluation-rejection.json"
        rejection = json.loads(rejection_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(rejection),
            {
                "artifact_type", "schema_version", "run_id", "started_at",
                "evaluation_id", "case_id", "status", "phase", "reason",
            },
        )
        self.assertEqual(rejection["status"], "rejected")
        self.assertEqual(rejection["phase"], "external-report-preflight")
        self.assertEqual(rejection["reason"]["code"], code)
        self.assertEqual(rejection["reason"]["stage"], stage)
        self.assertEqual(rejection["reason"]["report_index"], 1)
        self.assertEqual(rejection["reason"].get("field"), field)
        self.assertFalse((output / "review-evaluation.json").exists())
        serialized = json.dumps(rejection)
        for forbidden in (
            "materialized-request", "external_reports", "expected_sha256",
            "ci_provenance", "provenance_expectation", "provenance_policy",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_existing_gold_fixtures_are_sha256_pinned(self) -> None:
        pinned_sources = 0
        for manifest_path in (
            MANIFEST, RUNTIME_MANIFEST, HELD_OUT_MANIFEST, CROSS_RUN_MANIFEST,
            COHORT_MANIFEST, EXTERNAL_COHORT_MANIFEST,
        ):
            manifest = load_evaluation_manifest(manifest_path)
            for case in manifest["cases"]:
                for report in case.get("external_reports", []):
                    source = manifest_path.parent / report["source"]
                    pinned_sources += 1
                    self.assertEqual(
                        report["expected_sha256"],
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                        f"unpinned or stale external evaluation source: {source}",
                    )
                request_path = manifest_path.parent / case["request"]
                request = json.loads(request_path.read_text(encoding="utf-8"))
                for artifact in request["artifact_registry"]:
                    source = request_path.parent / artifact["source"]
                    if not source.is_file():
                        continue
                    pinned_sources += 1
                    self.assertEqual(
                        artifact.get("expected_sha256"),
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                        f"unpinned or stale evaluation source: {source}",
                    )
        self.assertEqual(pinned_sources, 29)

    def test_gold_evaluation_meets_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(MANIFEST, output)
            persisted = json.loads(
                (output / "review-evaluation.json").read_text(encoding="utf-8")
            )
            markdown = (output / "review-evaluation.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["case_count"], 14)
        self.assertEqual(result["check_count"], 30)
        self.assertEqual(result["repeat_runs"], 3)
        self.assertEqual(
            result["domain_check_counts"],
            {"can": 5, "core": 11, "dbc": 5, "dtc": 4, "uds": 5},
        )
        self.assertTrue(
            all(value == 1.0 for value in result["domain_check_accuracy"].values())
        )
        self.assertTrue(all(case["passed"] for case in result["cases"]))
        self.assertEqual(result["metrics"]["false_conflict_count"], 0)
        self.assertTrue(
            all(
                value == 1.0
                for key, value in result["metrics"].items()
                if key != "false_conflict_count"
            )
        )
        self.assertEqual(persisted["schema_version"], "review-evaluation-result-0.2")
        self.assertEqual(result["split_check_counts"], {"development": 30})
        self.assertIn("does not use an LLM judge", markdown)

    def test_runtime_evaluation_materializes_pinned_runner_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(RUNTIME_MANIFEST, output)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["case_count"], 3)
            self.assertEqual(result["check_count"], 3)
            self.assertEqual(result["split_check_counts"], {"runtime": 3})
            self.assertTrue(all(case["passed"] for case in result["cases"]))
            for case in result["cases"]:
                producer = case["producer"]
                report = output / case["case_id"] / "producer" / producer["report"]
                materialized = json.loads(
                    (output / case["case_id"] / "materialized-request.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertTrue(report.is_file())
                self.assertEqual(producer["status"], "passed")
                self.assertEqual(
                    producer["source_sha256"],
                    hashlib.sha256(report.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    materialized["artifact_registry"][0]["expected_sha256"],
                    producer["source_sha256"],
                )

    def test_independent_held_out_negative_set_meets_every_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_review_evaluation(HELD_OUT_MANIFEST, Path(directory))

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["case_count"], 3)
        self.assertEqual(result["check_count"], 3)
        self.assertEqual(result["split_check_counts"], {"held-out": 3})
        self.assertTrue(
            all(case["observed_status"] == "refused" for case in result["cases"])
        )
        self.assertEqual(result["metrics"]["false_conflict_count"], 0)

    def test_cross_run_evaluation_distinguishes_stability_and_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(CROSS_RUN_MANIFEST, output)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["schema_version"], "review-evaluation-result-0.6")
            self.assertEqual(result["case_count"], 7)
            self.assertEqual(result["check_count"], 7)
            self.assertEqual(result["split_check_counts"], {"cross-run": 7})
            self.assertEqual(result["metrics"]["conflict_recall"], 1.0)
            self.assertEqual(result["metrics"]["false_conflict_count"], 0)
            for case in result["cases"]:
                hashes = {
                    report["source_sha256"]
                    for report in case["producer"]["reports"]
                }
                self.assertEqual(len(hashes), 2)
                for report_evidence in case["producer"]["reports"]:
                    report_path = (
                        output / case["case_id"] / "producer" / report_evidence["report"]
                    )
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    self.assertEqual(
                        report_evidence["applicability_profile"],
                        report["applicability_profile"],
                    )
            drift = next(
                case for case in result["cases"]
                if case["case_id"] == "cross-run-can-drift"
            )
            self.assertEqual(drift["observed_status"], "refused")
            self.assertEqual(
                drift["observed_checks"], {"cross-run-can-drift": "conflicted"}
            )
            self.assertEqual(drift["citation_count"], 2)
            self.assertEqual(drift["producer"]["runs"], 2)
            for report_evidence in drift["producer"]["reports"]:
                report = output / drift["case_id"] / "producer" / report_evidence["report"]
                self.assertEqual(
                    report_evidence["source_sha256"],
                    hashlib.sha256(report.read_bytes()).hexdigest(),
                )
            mutated = json.loads(
                (
                    output
                    / drift["case_id"]
                    / "producer"
                    / "run-2"
                    / "can-runtime-report.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(mutated["scenarios"][0]["status"], "failed")
            for case_id in ("cross-run-uds-drift", "cross-run-dtc-drift"):
                domain_drift = next(
                    case for case in result["cases"] if case["case_id"] == case_id
                )
                self.assertEqual(domain_drift["observed_status"], "refused")
                self.assertEqual(set(domain_drift["observed_checks"].values()), {"conflicted"})
                self.assertEqual(domain_drift["citation_count"], 2)
            applicability = next(
                case for case in result["cases"]
                if case["case_id"] == "cross-run-applicability-mismatch"
            )
            self.assertEqual(applicability["observed_status"], "refused")
            self.assertEqual(
                applicability["observed_checks"],
                {"cross-run-applicability-mismatch": "blocked"},
            )
            self.assertEqual(
                applicability["observed_refusal_codes"],
                ["REVIEW-APPLICABILITY-MISMATCH"],
            )
            self.assertEqual(applicability["citation_count"], 0)
            profiles = [
                report["applicability_profile"]
                for report in applicability["producer"]["reports"]
            ]
            self.assertNotEqual(
                profiles[0]["software_version"], profiles[1]["software_version"]
            )
            self.assertEqual(
                profiles[0]["calibration_version"], profiles[1]["calibration_version"]
            )

    def test_cross_run_dynamic_fields_are_not_comparable(self) -> None:
        manifest = json.loads(CROSS_RUN_MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"] = [manifest["cases"][0]]
        manifest["cases"][0]["request"] = "requests/25-cross-run-dynamic-field.json"
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "evaluation.json"
            manifest["cases"][0]["request"] = str(
                (CROSS_RUN_MANIFEST.parent / manifest["cases"][0]["request"]).resolve()
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "dynamic field is not comparable"):
                run_review_evaluation(manifest_path, Path(directory) / "output")

    def test_three_run_cohort_emits_exact_candidate_drift_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(COHORT_MANIFEST, output)
            markdown = (output / "review-evaluation.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["schema_version"], "review-evaluation-result-0.8")
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(result["check_count"], 4)
        self.assertEqual(result["split_check_counts"], {"cohort": 4})
        self.assertEqual(
            result["drift_status_counts"],
            {"stable": 4, "drifted": 3, "not-comparable": 1},
        )
        self.assertEqual(
            result["domain_drift_status_counts"],
            {
                "can": {"stable": 2, "drifted": 1, "not-comparable": 1},
                "dtc": {"stable": 1, "drifted": 1, "not-comparable": 0},
                "uds": {"stable": 1, "drifted": 1, "not-comparable": 0},
            },
        )
        self.assertEqual(result["metrics"]["drift_catalog_accuracy"], 1.0)
        self.assertEqual(result["metrics"]["finding_preservation"], 1.0)
        self.assertTrue(all(case["passed"] for case in result["cases"]))
        drift = next(
            case for case in result["cases"]
            if case["case_id"] == "cohort-can-stable-and-drift"
        )
        mismatch = next(
            case for case in result["cases"]
            if case["case_id"] == "cohort-can-applicability-mismatch"
        )
        self.assertEqual(
            [item["status"] for item in drift["observed_drift_catalog"]],
            ["stable", "drifted"],
        )
        self.assertEqual(
            [item["status"] for item in mismatch["observed_drift_catalog"]],
            ["stable", "not-comparable"],
        )
        for case_id in (
            "cohort-uds-stable-and-drift",
            "cohort-dtc-stable-and-drift",
        ):
            case = next(
                item for item in result["cases"] if item["case_id"] == case_id
            )
            self.assertEqual(
                [item["status"] for item in case["observed_drift_catalog"]],
                ["stable", "drifted"],
            )
        for case in result["cases"]:
            self.assertEqual(case["producer"]["runs"], 3)
            self.assertEqual(len(case["producer"]["reports"]), 3)
        self.assertIn("## Drift catalog summary", markdown)
        self.assertIn("| `uds` | 1 | 1 | 0 |", markdown)
        self.assertIn("| `dtc` | 1 | 1 | 0 |", markdown)

    def test_external_cohort_verifies_pinned_reports_without_running_producer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_review_evaluation(EXTERNAL_COHORT_MANIFEST, output)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["schema_version"], "review-evaluation-result-1.3")
            self.assertEqual(result["drift_status_counts"], {
                "stable": 3, "drifted": 3, "not-comparable": 0,
            })
            self.assertEqual(set(result["domain_drift_status_counts"]), {
                "can", "uds", "dtc",
            })
            for case in result["cases"]:
                case_output = output / case["case_id"]
                materialized = json.loads(
                    (case_output / "materialized-request.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertNotIn("producer", case)
                self.assertEqual(case["external_reports"]["status"], "verified")
                self.assertEqual(case["external_reports"]["report_count"], 3)
                policy = case["external_reports"]["provenance_policy"]
                self.assertEqual(policy["status"], "enforced")
                self.assertEqual(policy["repository"], "public/window-control-fixture")
                self.assertFalse((case_output / "producer").exists())
                for artifact, report in zip(
                    materialized["artifact_registry"],
                    case["external_reports"]["reports"],
                ):
                    self.assertEqual(
                        artifact["expected_sha256"], report["source_sha256"]
                    )
                    self.assertEqual(
                        report["source_sha256"],
                        hashlib.sha256(Path(artifact["source"]).read_bytes()).hexdigest(),
                    )
                    self.assertEqual(report["ci_provenance"]["status"], "hash-bound")
                    self.assertIn(report["ci_provenance"]["provider"], {"example-ci"})
                    self.assertEqual(
                        report["ci_provenance"]["repository"], policy["repository"]
                    )
                    self.assertIn(
                        report["ci_provenance"]["job_id"], policy["allowed_job_ids"]
                    )
                    self.assertEqual(
                        report["provenance_expectation"]["status"], "matched"
                    )
                    for field in ("repository", "job_id", "commit_sha"):
                        self.assertEqual(
                            report["provenance_expectation"][field],
                            report["ci_provenance"][field],
                        )

    def test_external_cross_domain_cohort_requires_ci_provenance(self) -> None:
        manifest = json.loads(EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8"))
        fixture = json.loads(
            (EXTERNAL_COHORT_MANIFEST.parent / "fixtures/external-can-baseline.json")
            .read_text(encoding="utf-8")
        )
        fixture.pop("ci_provenance")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            report_path.write_text(json.dumps(fixture), encoding="utf-8")
            manifest["cases"] = [manifest["cases"][0]]
            case = manifest["cases"][0]
            case["request"] = str(
                (EXTERNAL_COHORT_MANIFEST.parent / case["request"]).resolve()
            )
            expectation = case["external_reports"][0]["provenance_expectation"]
            case["external_reports"][0] = {
                "source": str(report_path),
                "expected_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                "provenance_expectation": expectation,
            }
            for report in case["external_reports"][1:]:
                report["source"] = str(
                    (EXTERNAL_COHORT_MANIFEST.parent / report["source"]).resolve()
                )
            manifest_path = root / "evaluation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid ci_provenance"):
                run_review_evaluation(manifest_path, root / "output")
            self.assert_preflight_rejection(
                root / "output",
                code="invalid-ci-provenance",
                stage="provenance",
            )

    def test_external_cohort_requires_explicit_provenance_expectation(self) -> None:
        manifest = json.loads(EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"][0]["external_reports"][0].pop("provenance_expectation")
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "evaluation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid external report"):
                load_evaluation_manifest(manifest_path)

    def test_external_cohort_fails_closed_on_provenance_expectation_mismatch(self) -> None:
        mismatches = {
            "repository": "unexpected/repository",
            "job_id": "unexpected-job",
            "commit_sha": "f" * 40,
        }
        for field, value in mismatches.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = json.loads(
                    EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8")
                )
                manifest["cases"] = [manifest["cases"][0]]
                case = manifest["cases"][0]
                case["request"] = str(
                    (EXTERNAL_COHORT_MANIFEST.parent / case["request"]).resolve()
                )
                for report in case["external_reports"]:
                    report["source"] = str(
                        (EXTERNAL_COHORT_MANIFEST.parent / report["source"]).resolve()
                    )
                case["external_reports"][0]["provenance_expectation"][field] = value
                manifest_path = root / "evaluation.json"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                with self.assertRaisesRegex(
                    ValueError, f"provenance expectation mismatch: {field}"
                ):
                    run_review_evaluation(manifest_path, root / "output")
                self.assertFalse(
                    (root / "output" / case["case_id"] / "materialized-request.json").exists()
                )
                self.assert_preflight_rejection(
                    root / "output",
                    code="provenance-expectation-mismatch",
                    stage="expectation",
                    field=field,
                )

    def test_external_cohort_requires_valid_provenance_policy(self) -> None:
        invalid_policies = (
            None,
            {"repository": "public/window-control-fixture", "allowed_job_ids": []},
            {
                "repository": "public/window-control-fixture",
                "allowed_job_ids": ["can-baseline", "can-baseline"],
            },
        )
        for policy in invalid_policies:
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                manifest = json.loads(
                    EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8")
                )
                if policy is None:
                    manifest["cases"][0].pop("provenance_policy")
                else:
                    manifest["cases"][0]["provenance_policy"] = policy
                manifest_path = Path(directory) / "evaluation.json"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "invalid provenance_policy"):
                    load_evaluation_manifest(manifest_path)

    def test_external_cohort_fails_closed_on_provenance_policy_violation(self) -> None:
        violations = {
            "repository": {"repository": "unexpected/repository"},
            "job_id": {"allowed_job_ids": ["can-candidate-stable"]},
        }
        for field, update in violations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = json.loads(
                    EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8")
                )
                manifest["cases"] = [manifest["cases"][0]]
                case = manifest["cases"][0]
                case["request"] = str(
                    (EXTERNAL_COHORT_MANIFEST.parent / case["request"]).resolve()
                )
                for report in case["external_reports"]:
                    report["source"] = str(
                        (EXTERNAL_COHORT_MANIFEST.parent / report["source"]).resolve()
                    )
                case["provenance_policy"].update(update)
                manifest_path = root / "evaluation.json"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                with self.assertRaisesRegex(
                    ValueError, f"violates provenance policy: {field}"
                ):
                    run_review_evaluation(manifest_path, root / "output")
                self.assertFalse(
                    (root / "output" / case["case_id"] / "materialized-request.json").exists()
                )
                self.assert_preflight_rejection(
                    root / "output",
                    code="provenance-policy-violation",
                    stage="policy",
                    field=field,
                )

    def test_external_cohort_fails_closed_on_stale_sha256(self) -> None:
        manifest = json.loads(EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"][0]["external_reports"][0]["expected_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "evaluation.json"
            manifest["cases"][0]["request"] = str(
                (EXTERNAL_COHORT_MANIFEST.parent / manifest["cases"][0]["request"]).resolve()
            )
            for report in manifest["cases"][0]["external_reports"]:
                report["source"] = str(
                    (EXTERNAL_COHORT_MANIFEST.parent / report["source"]).resolve()
                )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "external report SHA-256 mismatch"):
                run_review_evaluation(manifest_path, Path(directory) / "output")
            self.assert_preflight_rejection(
                Path(directory) / "output",
                code="sha256-mismatch",
                stage="integrity",
            )

    def test_external_reports_are_versioned_and_mutually_exclusive_with_producer(self) -> None:
        manifest = json.loads(EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "evaluation.json"
            manifest["schema_version"] = "review-evaluation-0.8"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "external_reports requires schema 0.9"):
                load_evaluation_manifest(manifest_path)

            manifest["schema_version"] = "review-evaluation-0.9"
            manifest["cases"][0]["producer"] = {
                "kind": "can-lab",
                "input": "input.dbc",
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot combine producer and external_reports"):
                load_evaluation_manifest(manifest_path)

    def test_external_report_10_11_and_12_manifests_remain_backward_compatible(self) -> None:
        manifest = json.loads(EXTERNAL_COHORT_MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "evaluation.json"
            manifest["schema_version"] = "review-evaluation-1.2"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_evaluation_manifest(manifest_path)
            self.assertEqual(loaded["schema_version"], "review-evaluation-1.2")

            for case in manifest["cases"]:
                case.pop("provenance_policy")
            manifest["schema_version"] = "review-evaluation-1.1"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_evaluation_manifest(manifest_path)
            self.assertEqual(loaded["schema_version"], "review-evaluation-1.1")

            manifest["schema_version"] = "review-evaluation-1.0"
            for case in manifest["cases"]:
                for report in case["external_reports"]:
                    report.pop("provenance_expectation")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_evaluation_manifest(manifest_path)
            self.assertEqual(loaded["schema_version"], "review-evaluation-1.0")

    def test_rejects_mutation_outside_producer_stable_field_allowlist(self) -> None:
        manifest = json.loads(CROSS_RUN_MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"][0]["producer"]["mutations"] = [
            {"run": 2, "pointer": "/run_id", "value": "forged"}
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsafe producer mutation"):
                load_evaluation_manifest(path)

            manifest = json.loads(CROSS_RUN_MANIFEST.read_text(encoding="utf-8"))
            manifest["schema_version"] = "review-evaluation-0.3"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires schema 0.4 or newer"):
                load_evaluation_manifest(path)

    def test_three_run_producer_requires_evaluation_07(self) -> None:
        manifest = json.loads(COHORT_MANIFEST.read_text(encoding="utf-8"))
        manifest["schema_version"] = "review-evaluation-0.6"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "three-run producer requires schema 0.7 or newer"):
                load_evaluation_manifest(path)

    def test_rejects_duplicate_evaluation_case(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"].append(manifest["cases"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate.*case_id"):
                load_evaluation_manifest(path)

    def test_v01_manifest_defaults_cases_to_core_domain(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["schema_version"] = "review-evaluation-0.1"
        for case in manifest["cases"]:
            case.pop("domain")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            loaded = load_evaluation_manifest(path)

        self.assertTrue(all(case["domain"] == "core" for case in loaded["cases"]))
        self.assertTrue(all(case["split"] == "development" for case in loaded["cases"]))

    def test_rejects_unlisted_runtime_producer(self) -> None:
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        manifest["cases"][0]["producer"]["kind"] = "shell"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsupported producer"):
                load_evaluation_manifest(path)


if __name__ == "__main__":
    unittest.main()
