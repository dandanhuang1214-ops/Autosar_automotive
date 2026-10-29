from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from automotive_workbench.davinci_workflow import assess_workflow, verify_workflow


class DaVinciWorkflowTests(unittest.TestCase):
    def test_layered_result_preserves_failures_and_rejects_tamper(self) -> None:
        reports = {
            "mapping": {"contract_version": "davinci-mapping-audit-0.1", "status": "passed",
                        "summary": {"total": 2, "resolved": 2}},
            "cfg": {"contract_version": "cfg-validation-summary-0.1", "status": "attention-required",
                    "validation_counts": {"errors": 1, "warnings": 0}, "generation": {"state": "ERROR"}},
            "communication": {"schema_version": "ecuc-communication-0.1", "status": "resolved-in-scope",
                              "paths": [{"path": 1}]},
            "review": {"schema_version": "ecuc-engineering-review-0.1", "status": "attention-required",
                       "summary": {"structural_findings": 3}},
        }
        with TemporaryDirectory() as directory:
            base = Path(directory)
            paths = {key: base / f"{key}.json" for key in reports}
            for key, path in paths.items():
                path.write_text(json.dumps(reports[key]), encoding="utf-8")
            output = base / "assessment.json"
            with patch("automotive_workbench.davinci_workflow.verify_mapping_audit"), \
                 patch("automotive_workbench.davinci_workflow.verify_cfg_report"), \
                 patch("automotive_workbench.davinci_workflow.verify_communication"), \
                 patch("automotive_workbench.davinci_workflow.verify_review"):
                result = assess_workflow(paths["mapping"], paths["cfg"], paths["communication"], paths["review"], output)
                self.assertEqual(result["status"], "attention-required")
                self.assertEqual(result["layers"]["cfg_validation"]["errors"], 1)
                self.assertEqual(result["layers"]["can_bus_execution"]["status"], "unassessed")
                self.assertEqual(verify_workflow(output)["status"], "passed")
                altered = json.loads(output.read_text(encoding="utf-8"))
                altered["layers"]["cfg_validation"]["errors"] = 0
                output.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "does not match"):
                    verify_workflow(output)
