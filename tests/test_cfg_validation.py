from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from automotive_workbench.cfg_validation import inspect_cfg_report, verify_cfg_report


XML = '''<?xml version="1.0" encoding="UTF-8"?>
<DaVinciExecutionReport name="Generation Execution Report">
  <ValidationResults fatalerrors="0" errors="1" warnings="1" improvements="0" infos="0">
    <ValidationResultId id="00022" message="Missing parameter value" origin="CAN">
      <ValidationResult severity="Error"><Description>missing</Description></ValidationResult>
      <ValidationResult severity="Warning"><Description>check</Description></ValidationResult>
    </ValidationResultId>
  </ValidationResults>
  <GenerationProcessResult result="ERROR">
    <GenerationResult generationtype="GENERATOR"><Name>Can</Name><State>FAILED</State></GenerationResult>
  </GenerationProcessResult>
</DaVinciExecutionReport>'''


class CfgValidationTests(unittest.TestCase):
    def test_source_bound_summary_and_tamper_rejection(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "validation.xml"
            report = Path(directory) / "summary.json"
            source.write_text(XML, encoding="utf-8")
            result = inspect_cfg_report(source, report)
            self.assertEqual(result["status"], "attention-required")
            self.assertEqual(result["validation_counts"]["errors"], 1)
            self.assertEqual(result["generation"]["generators"], [{"name": "Can", "state": "FAILED"}])
            self.assertEqual(verify_cfg_report(report)["status"], "passed")
            altered = json.loads(report.read_text(encoding="utf-8"))
            altered["validation_counts"]["errors"] = 0
            report.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                verify_cfg_report(report)

    def test_declared_count_mismatch_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "validation.xml"
            source.write_text(XML.replace('errors="1"', 'errors="0"'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "counts disagree"):
                inspect_cfg_report(source, Path(directory) / "summary.json")

    def test_dtd_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "validation.xml"
            source.write_text('<!DOCTYPE x [<!ENTITY y "z">]>' + XML, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DTD"):
                inspect_cfg_report(source, Path(directory) / "summary.json")
