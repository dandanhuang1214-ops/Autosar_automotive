from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    load_evidence_bundle_manifest,
    verify_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceBundleTests(unittest.TestCase):
    def _communication_bundle(self, root: Path) -> tuple[Path, Path]:
        bundle = root / "communication"
        run_communication_chain(DBC, INTENT, bundle)
        manifest_path = root / "manifest.json"
        create_evidence_bundle_manifest(
            bundle,
            manifest_path,
            "workbench run-communication-chain",
            base=ROOT,
        )
        return bundle, manifest_path

    def test_indexes_communication_bundle_with_portable_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "communication"
            run_communication_chain(DBC, INTENT, bundle)
            manifest_path = root / "manifest.json"

            manifest = create_evidence_bundle_manifest(
                bundle,
                manifest_path,
                "workbench run-communication-chain",
                bundle_id="communication-demo",
                base=ROOT,
            )

        self.assertEqual(manifest["schema_version"], "evidence-bundle-manifest-0.1")
        self.assertEqual(manifest["bundle_id"], "communication-demo")
        paths = [artifact["relative_path"] for artifact in manifest["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(manifest["artifact_count"], 7)
        combined = next(
            artifact
            for artifact in manifest["artifacts"]
            if artifact["relative_path"] == "communication-evidence-report.json"
        )
        self.assertEqual(combined["artifact_type"], "communication-chain-evidence")
        self.assertEqual(combined["schema_version"], "communication-evidence-0.2")
        self.assertEqual(
            {(item["kind"], item["ref"]) for item in combined["depends_on"]},
            {
                ("artifact", "runtime/can-runtime-report.json"),
                ("external", "examples/window_control/bsw_intent.json"),
                ("external", "examples/window_control/window_control.dbc"),
            },
        )
        self.assertNotIn(str(root), json.dumps(manifest))

    def test_rejects_manifest_inside_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            bundle.mkdir()
            (bundle / "report.md").write_text("# report\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside"):
                create_evidence_bundle_manifest(
                    bundle,
                    bundle / "manifest.json",
                    "test producer",
                )

    def test_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            target = bundle / "report.md"
            target.write_text("# report\n", encoding="utf-8")
            try:
                (bundle / "report-link.md").symlink_to(target)
            except OSError:
                self.skipTest("symlinks are not available on this platform")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                create_evidence_bundle_manifest(
                    bundle,
                    root / "manifest.json",
                    "test producer",
                )

    def test_rejects_declared_dependency_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            report = {
                "artifact_type": "derived-report",
                "source_artifacts": [
                    {"source": str(DBC), "sha256": "0" * 64}
                ],
            }
            (bundle / "report.json").write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                create_evidence_bundle_manifest(
                    bundle,
                    root / "manifest.json",
                    "test producer",
                    base=ROOT,
                )

    def test_rejects_dependency_outside_portable_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            outside = root / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            report = {
                "source_artifacts": [
                    {
                        "source": str(outside),
                        "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    }
                ]
            }
            (bundle / "report.json").write_text(json.dumps(report), encoding="utf-8")
            base = root / "portable-base"
            base.mkdir()
            with self.assertRaisesRegex(ValueError, "escapes"):
                create_evidence_bundle_manifest(
                    bundle,
                    root / "manifest.json",
                    "test producer",
                    base=base,
                )

    def test_verifies_unchanged_bundle_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, manifest_path = self._communication_bundle(root)
            result = verify_evidence_bundle(
                bundle, manifest_path, root / "verification", base=ROOT
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified_artifact_count"], 7)
        self.assertEqual((result["verified_dependency_count"], result["dependency_count"]), (3, 3))
        self.assertEqual(result["findings"], [])

    def test_reports_missing_unexpected_and_same_size_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, manifest_path = self._communication_bundle(root)
            target = bundle / "communication-evidence-report.md"
            content = target.read_bytes()
            target.write_bytes(bytes([content[0] ^ 1]) + content[1:])
            (bundle / "static-validation.json").unlink()
            (bundle / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

            result = verify_evidence_bundle(
                bundle, manifest_path, root / "verification", base=ROOT
            )

        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(result["status"], "failed")
        self.assertIn("EVIDENCE-FILE-MISSING", codes)
        self.assertIn("EVIDENCE-FILE-UNEXPECTED", codes)
        self.assertIn("EVIDENCE-SHA256-MISMATCH", codes)

    def test_reports_external_dependency_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base"
            source = base / "input.json"
            source.parent.mkdir()
            source.write_text('{"version":1}\n', encoding="utf-8")
            bundle = root / "bundle"
            bundle.mkdir()
            report = {
                "source_artifacts": [
                    {"source": "input.json", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                ]
            }
            (bundle / "report.json").write_text(json.dumps(report), encoding="utf-8")
            manifest = root / "manifest.json"
            create_evidence_bundle_manifest(bundle, manifest, "test", base=base)
            source.write_text('{"version":2}\n', encoding="utf-8")

            result = verify_evidence_bundle(
                bundle, manifest, root / "verification", base=base
            )

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "EVIDENCE-DEPENDENCY-SHA256-MISMATCH",
            {finding["code"] for finding in result["findings"]},
        )

    def test_rejects_unsafe_or_inconsistent_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, manifest_path = self._communication_bundle(root)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["artifacts"][0]["relative_path"] = "../escape.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "portable relative path"):
                load_evidence_bundle_manifest(manifest_path)

    def test_rejects_boolean_manifest_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "empty.md").write_bytes(b"")
            manifest_path = root / "manifest.json"
            manifest = create_evidence_bundle_manifest(
                bundle, manifest_path, "test producer"
            )

            for field, value in (
                ("artifact_count", True),
                ("total_bytes", False),
                ("size_bytes", False),
            ):
                with self.subTest(field=field):
                    payload = json.loads(json.dumps(manifest))
                    if field == "size_bytes":
                        payload["artifacts"][0][field] = value
                    else:
                        payload[field] = value
                    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "count|bytes|size"):
                        load_evidence_bundle_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
