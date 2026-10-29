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
    report.write_text(json.dumps({"artifact_type": "project-acceptance", "schema_version": "project-acceptance-0.3",
                                  "name": "Demo acceptance", "status": "passed", "stages": {"communication": "communication.json"},
                                  "requirements": [{"id": "TX_VECTOR", "status": "passed", "actual": "passed",
                                                    "evidence": {"path": "communication.json", "sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
                                                                 "pointer": "/status"}}]}), encoding="utf-8")
    bindings = root / "bindings.json"
    bindings.write_text(json.dumps({"schema_version": "cross-tool-acceptance-bindings-0.1", "project_name": "Demo acceptance",
                                    "links": [{"port": "/Components/Node/Out", "data_element": "/Interfaces/State/Ready",
                                               "com_signal": old["links"][0]["com_signal"], "acceptance_ids": ["TX_VECTOR"]}]}), encoding="utf-8")
    return impact, bindings, report, stage, old["links"][0]["com_signal"]


class CrossToolAcceptanceTests(unittest.TestCase):
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
