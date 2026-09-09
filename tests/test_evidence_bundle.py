from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.evidence_bundle import create_evidence_bundle_manifest


ROOT = Path(__file__).resolve().parents[1]
DBC = ROOT / "examples" / "window_control" / "window_control.dbc"
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class EvidenceBundleTests(unittest.TestCase):
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
        self.assertEqual(manifest["artifact_count"], 5)
        combined = next(
            artifact
            for artifact in manifest["artifacts"]
            if artifact["relative_path"] == "communication-evidence-report.json"
        )
        self.assertEqual(combined["artifact_type"], "communication-chain-evidence")
        self.assertEqual(combined["schema_version"], "communication-evidence-0.1")
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


if __name__ == "__main__":
    unittest.main()
