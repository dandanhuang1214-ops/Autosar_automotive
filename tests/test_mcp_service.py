"""Real MCP SDK calls against a replay-verified ECUC project report."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.can_io import BusConfig
from automotive_workbench.mcp_evidence_client import validate_endpoint
from automotive_workbench.project_workflow import run_project

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples/ecuc_acceptance/transmitter.project.json"


@unittest.skipUnless(importlib.util.find_spec("mcp"), "optional MCP SDK is not installed")
class McpServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        run_project(PROJECT, cls.root / "run", BusConfig("virtual", "mcp-test"))
        cls.report = cls.root / "run/bundle/project-report.json"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_sdk_discovers_and_calls_read_only_project_tools(self) -> None:
        from mcp import Client
        from automotive_workbench.mcp_service import build_server

        async def exercise() -> None:
            async with Client(build_server(self.root), mode="2026-07-28",
                              read_timeout_seconds=30) as client:
                tools = await client.list_tools()
                names = {item.name for item in tools.tools}
                self.assertEqual(names, {"verify_project_report", "project_evidence"})
                evidence = await client.call_tool("project_evidence", {
                    "report_path": str(self.report), "question": "通信验收状态是什么？",
                })
                self.assertFalse(evidence.is_error)
                payload = evidence.structured_content
                self.assertEqual(len(payload["report_sha256"]), 64)
                self.assertEqual(payload["project_status"], "passed")
                self.assertGreater(payload["available_fact_count"], 0)
                self.assertLessEqual(len(payload["facts"]), 16)
                self.assertTrue(all(item.annotations.read_only_hint for item in tools.tools))

        asyncio.run(exercise())

    def test_report_outside_configured_root_is_refused(self) -> None:
        from automotive_workbench.mcp_service import _report_path

        with self.assertRaisesRegex(ValueError, "outside the configured root"):
            _report_path(self.root, str(PROJECT))

    def test_web_host_only_accepts_loopback_mcp_endpoint(self) -> None:
        self.assertEqual(validate_endpoint("http://127.0.0.1:8768/mcp"),
                         "http://127.0.0.1:8768/mcp")
        for value in ("https://example.com/mcp", "http://192.0.2.1:8768/mcp",
                      "http://127.0.0.1:8768/other", "http://127.0.0.1:8768/mcp?x=1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_endpoint(value)


if __name__ == "__main__":
    unittest.main()
