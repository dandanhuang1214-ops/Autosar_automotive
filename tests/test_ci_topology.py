from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_ci_topology import check_topology


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CiTopologyTests(unittest.TestCase):
    def test_current_workflow_matches_frozen_topology(self) -> None:
        result = check_topology(WORKFLOW)

        self.assertEqual(result["job_count"], 4)
        self.assertEqual(result["matrix_job_count"], 3)
        self.assertEqual(result["controlled_failure_count"], 4)

    def test_rejects_controlled_failure_moved_into_runtime_job(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        runtime_marker = "  runtime-evidence:\n"
        mutated = text.replace(
            runtime_marker,
            runtime_marker + "    continue-on-error: true\n",
            1,
        )

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ci.yml"
            path.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside rejection job"):
                check_topology(path)

    def test_rejects_runtime_job_without_core_dependency(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8").replace(
            "  runtime-evidence:\n    needs: core-contracts\n",
            "  runtime-evidence:\n",
            1,
        )

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ci.yml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must depend on core-contracts"):
                check_topology(path)
