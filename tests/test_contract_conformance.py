from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from automotive_workbench.evidence_bundle import load_evidence_bundle_manifest
from scripts.check_json import validate_checked_in_json


ROOT = Path(__file__).resolve().parents[1]


class ContractConformanceTests(unittest.TestCase):
    def test_checked_in_self_describing_examples_match_their_schemas(self) -> None:
        schema_count, validated, syntax_only = validate_checked_in_json(
            ROOT, verbose=False
        )
        self.assertEqual(schema_count, 27)
        self.assertGreaterEqual(validated, 42)
        self.assertGreaterEqual(syntax_only, 1)

    def test_json_boolean_does_not_conform_to_integer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            (root / "examples").mkdir()
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.invalid/count.schema.json",
                "type": "object",
                "required": ["schema_version", "count"],
                "properties": {
                    "schema_version": {"const": "count-0.1"},
                    "count": {"type": "integer"},
                },
                "additionalProperties": False,
            }
            (root / "schemas" / "count.schema.json").write_text(
                json.dumps(schema), encoding="utf-8"
            )
            (root / "examples" / "invalid.json").write_text(
                json.dumps({"schema_version": "count-0.1", "count": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Schema validation failed"):
                validate_checked_in_json(root, verbose=False)

    def test_manifest_schema_and_loader_both_reject_boolean_count(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "evidence-bundle-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = {
            "artifact_type": "evidence-bundle-manifest",
            "schema_version": "evidence-bundle-manifest-0.1",
            "bundle_id": "bundle-test",
            "created_at": "2026-09-10T00:00:00Z",
            "producer": "contract-conformance-test",
            "artifact_count": True,
            "total_bytes": 0,
            "artifacts": [
                {
                    "artifact_id": "empty.json",
                    "relative_path": "empty.json",
                    "media_type": "application/json",
                    "artifact_type": "unknown-json",
                    "schema_version": None,
                    "size_bytes": 0,
                    "sha256": "0" * 64,
                    "depends_on": [],
                }
            ],
        }
        validator = validator_for(schema)(schema, format_checker=FormatChecker())
        self.assertTrue(list(validator.iter_errors(manifest)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact_count"):
                load_evidence_bundle_manifest(path)


if __name__ == "__main__":
    unittest.main()
