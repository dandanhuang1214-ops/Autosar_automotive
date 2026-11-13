"""Frozen Agent questions must bind to real source chunks before model contact."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_ai_platform_agent_cohort


class AgentCohortPreflightTests(unittest.TestCase):
    def test_unknown_target_chunk_stops_before_server_contact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_raw = b'{"chunks":[{"id":"chunk.real.K001"}]}'
            graph_hash = hashlib.sha256(graph_raw).hexdigest()
            graph_path = root / "output" / "knowledge-chat" / "snapshots" / graph_hash / "graph.json"
            graph_path.parent.mkdir(parents=True)
            graph_path.write_bytes(graph_raw)
            cohort_path = root / "cohort.json"
            cohort_path.write_text(json.dumps({
                "graph_sha256": graph_hash,
                "project_report_sha256": None,
                "cases": [{"id": "bad", "goal": "a new question", "report": None,
                           "target_chunk_id": "chunk.imaginary.K001"}],
            }), encoding="utf-8")
            argv = ["runner", "--server-url", "http://127.0.0.1:8767", "--mode", "agent",
                    "--cohort", str(cohort_path), "--output", str(root / "result.json")]
            with (patch.object(sys, "argv", argv),
                  patch.object(run_ai_platform_agent_cohort, "ROOT", root),
                  patch.object(run_ai_platform_agent_cohort, "_get",
                               side_effect=AssertionError("server contact before source validation"))):
                with self.assertRaisesRegex(ValueError, "target chunk"):
                    run_ai_platform_agent_cohort.main()


if __name__ == "__main__":
    unittest.main()
