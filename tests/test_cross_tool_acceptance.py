from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from automotive_workbench.cross_tool_acceptance import assess_acceptance, verify_acceptance
from automotive_workbench.cross_tool_trace import compare_traces, trace_cross_tool
from automotive_workbench.cli import main
from automotive_workbench.project_ecuc import capture, run
from tests.test_cross_tool_trace import ROOT, fixture


def scenario(root: Path) -> tuple[Path, Path, Path, Path, str]:
    source = ROOT / "tests/fixtures/ecuc-communication"
    before, after = root / "before", root / "after"
    fixture(before, source)
    fixture(after, source, signal="Alternate")
    old = trace_cross_tool(before / "mapping.json", before / "system.arxml", before / "demo.dpa", before / "trace.json")
    trace_cross_tool(after / "mapping.json", after / "system.arxml", after / "demo.dpa", after / "trace.json")
    impact = root / "impact.json"
    compare_traces(before / "trace.json", after / "trace.json", impact)
    project_dir = root / "acceptance"
    project_dir.mkdir()
    stage = project_dir / "communication.json"
    stage.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    report = project_dir / "project-report.json"
    before_hash = old["inputs"]["project"]["sha256"]
    after_hash = json.loads((after / "trace.json").read_text(encoding="utf-8"))["inputs"]["project"]["sha256"]
    report.write_text(json.dumps({"artifact_type": "project-acceptance", "schema_version": "project-acceptance-0.3",
                                  "name": "Demo acceptance", "status": "passed", "stages": {"communication": "communication.json"},
                                  "source_artifacts": [{"source": "bundle/ecuc/before/snapshot/demo.dpa", "sha256": before_hash},
                                                       {"source": "bundle/ecuc/after/snapshot/demo.dpa", "sha256": after_hash}],
                                  "requirements": [{"id": "TX_VECTOR", "status": "passed", "actual": "passed",
                                                    "evidence": {"path": "communication.json", "sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
                                                                 "pointer": "/status"}}]}), encoding="utf-8")
    bindings = root / "bindings.json"
    bindings.write_text(json.dumps({"schema_version": "cross-tool-acceptance-bindings-0.1", "project_name": "Demo acceptance",
                                    "links": [{"port": "/Components/Node/Out", "data_element": "/Interfaces/State/Ready",
                                               "com_signal": old["links"][0]["com_signal"], "acceptance_ids": ["TX_VECTOR"]}]}), encoding="utf-8")
    return impact, bindings, report, stage, old["links"][0]["com_signal"]


class CrossToolAcceptanceTests(unittest.TestCase):
    def test_semantic_snapshot_with_real_isolated_project_bundle(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            impact, bindings, _, _, _ = scenario(root)
            declaration = {"schema_version": "workbench-project-0.6", "name": "Demo acceptance",
                           "comparison_key": "cross-tool-snapshot-test",
                           "inputs": {role: {"project": f"{side}/demo.dpa", "applications": [], "tool_logs": []}
                                      for role, side in (("baseline", "before"), ("candidate", "after"))},
                           "requirements": [{"id": "TX_VECTOR", "text": "Communication structure",
                                             "stage": "ecuc", "pointer": "/checks/communication/status",
                                             "expected": "passed"}]}
            declaration_path = root / "test.project.json"
            declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
            package = root / "project-package"
            run(declaration, capture(declaration_path, declaration, declaration_path.read_bytes()), package)
            report = package / "bundle/project-report.json"
            output = root / "semantic.json"
            result = assess_acceptance(impact, bindings, report, output, strict_semantics=True)
            self.assertEqual(result["contract_version"], "cross-tool-acceptance-impact-0.3")
            self.assertEqual(result["status"], "rerun-required")
            self.assertEqual(result["semantic_consistency"]["before"]["status"], "resolved-in-scope")
            self.assertIn("modules.arxml", result["ecuc_source_sha256"]["after"])
            self.assertEqual(verify_acceptance(output)["status"], "passed")

            system = root / "after/system.arxml"
            original_system = system.read_bytes()
            system.write_bytes(original_system.replace(b"/Signal/Alternate", b"/Signal/Unknown"))
            trace_cross_tool(root / "after/mapping.json", system, root / "after/demo.dpa", root / "after/trace.json")
            compare_traces(root / "before/trace.json", root / "after/trace.json", impact)
            unresolved = assess_acceptance(impact, bindings, report, root / "unresolved.json", strict_semantics=True)
            self.assertEqual(unresolved["status"], "attention-required")
            self.assertEqual(unresolved["semantic_consistency"]["after"]["links"][0]["status"], "unassessed")
            system.write_bytes(original_system)

            # The DPA remains identical while an ECUC module outside the snapshot changes.
            module = root / "after/modules.arxml"
            module.write_bytes(module.read_bytes().replace(b"ComSystemTemplateSystemSignalRef", b"ComSystemTemplateOtherRef"))
            trace_cross_tool(root / "after/mapping.json", root / "after/system.arxml",
                             root / "after/demo.dpa", root / "after/trace.json")
            compare_traces(root / "before/trace.json", root / "after/trace.json", impact)
            legacy = assess_acceptance(impact, bindings, report, root / "dpa-only.json", strict_source=True)
            self.assertEqual(legacy["contract_version"], "cross-tool-acceptance-impact-0.2")
            with self.assertRaisesRegex(ValueError, "after ECUC source modules.arxml differs"):
                assess_acceptance(impact, bindings, report, root / "drift.json", strict_semantics=True)

    def test_strict_project_source_provenance(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            impact, bindings, report, _, _ = scenario(root)
            output = root / "strict.json"
            with patch("automotive_workbench.cross_tool_acceptance.verify_ecuc_project", return_value={"status": "passed"}):
                result = assess_acceptance(impact, bindings, report, output, strict_source=True)
                self.assertEqual(result["contract_version"], "cross-tool-acceptance-impact-0.2")
                self.assertEqual(result["ecuc_source_sha256"]["before"], result["ecuc_source_sha256"]["after"])
                self.assertEqual(verify_acceptance(output)["status"], "passed")
                raw = json.loads(report.read_text(encoding="utf-8"))
                raw["source_artifacts"][1]["sha256"] = "0" * 64
                report.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "after ECUC DPA differs"):
                    assess_acceptance(impact, bindings, report, root / "wrong.json", strict_source=True)

    def test_cli_returns_attention_exit_for_required_rerun(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            impact, bindings, report, _, _ = scenario(root)
            args = ["workbench", "assess-cross-tool-acceptance", "--impact", str(impact),
                    "--bindings", str(bindings), "--project-report", str(report),
                    "--output", str(root / "result.json")]
            with patch("sys.argv", args), redirect_stdout(StringIO()):
                self.assertEqual(main(), 2)

    def test_previous_evidence_is_bound_but_rerun_required(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            impact, bindings, report, stage, _ = scenario(root)
            output = root / "acceptance-impact.json"
            result = assess_acceptance(impact, bindings, report, output)
            self.assertEqual(result["status"], "rerun-required")
            self.assertEqual(result["affected"][0]["acceptance"][0]["previous_status"], "passed")
            self.assertTrue(result["affected"][0]["acceptance"][0]["rerun_required"])
            self.assertEqual(verify_acceptance(output)["status"], "passed")
            stage.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_acceptance(output)

    def test_unbound_change_and_false_com_binding(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            impact, bindings, report, _, _ = scenario(root)
            raw = json.loads(bindings.read_text(encoding="utf-8"))
            raw["links"] = []
            bindings.write_text(json.dumps(raw), encoding="utf-8")
            result = assess_acceptance(impact, bindings, report, root / "unbound.json")
            self.assertEqual(result["status"], "attention-required")
            self.assertEqual(len(result["unbound"]), 1)
            raw["links"] = [{"port": "/Components/Node/Out", "data_element": "/Interfaces/State/Ready",
                             "com_signal": "/Invented/ComSignal", "acceptance_ids": ["TX_VECTOR"]}]
            bindings.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ComSignal"):
                assess_acceptance(impact, bindings, report, root / "invalid.json")
