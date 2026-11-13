"""Independent graph, MCP, and combined read-only Agent paths."""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from automotive_workbench.ai_platform_agent import run_readonly_agent, verify_trace
from automotive_workbench.knowledge_graph_workspace import import_graph
from automotive_workbench.mcp_service import VERSION as MCP_VERSION
from automotive_workbench.knowledge_chat_server import WorkspaceServer
from automotive_workbench.model_client import ToolCompletion


class ScriptedClient:
    def __init__(self, actions: list[dict[str, object]]) -> None:
        self.actions = list(actions)
        self.requests: list[dict] = []

    def complete(self, payload: dict) -> dict:
        self.requests.append(payload)
        action = self.actions.pop(0)
        return {"done": True, "done_reason": "stop", "model": payload["model"],
                "message": {"role": "assistant", "content": json.dumps(action)},
                "prompt_eval_count": 50, "eval_count": 20,
                "response_id": "scripted-" + str(len(self.requests))}

    def identity(self, _model: str) -> dict:
        return {"digest": "f" * 64}

    def service_version(self) -> str:
        return "scripted-1"


class NativeScriptedClient:
    def __init__(self, calls: list[tuple[str, dict]]) -> None:
        self.calls = list(calls)
        self.requests: list[dict] = []

    def complete_tool_call(self, **request: object) -> ToolCompletion:
        self.requests.append(request)
        name, arguments = self.calls.pop(0)
        return ToolCompletion(name=name, arguments=arguments, content="",
                              input_tokens=50, output_tokens=20,
                              raw={"done": True, "done_reason": "stop",
                                   "model": request["model"],
                                   "message": {"role": "assistant", "content": "",
                                               "tool_calls": [{"function": {
                                                   "name": name, "arguments": arguments}}]},
                                   "prompt_eval_count": 50, "eval_count": 20})


def action(name: str, *, query: str = "", answer: str = "", ids: list[str] | None = None) -> dict:
    return {"action": name, "query": query, "answer": answer, "evidence_ids": ids or []}


def graph_fixture(root: Path) -> str:
    source = b"# CanIf\nCanIf does not parse UDS service 0x22.\n"
    graph = {"schemaVersion": "1.0", "title": "Synthetic graph",
             "nodes": [{"id": "K001", "label": "CanIf", "summary": "Candidate CanIf boundary",
                        "aliases": "CAN interface", "status": "candidate",
                        "sourceDocuments": ["doc1"], "claimIds": ["C001"]}],
             "edges": [],
             "claims": [{"id": "C001", "entityIds": ["K001"],
                         "sourceChunkIds": ["T001"], "status": "candidate"}],
             "chunks": [{"id": "T001", "sourceDocument": "doc1", "entityIds": ["K001"],
                         "text": "CanIf does not parse UDS service 0x22.", "status": "candidate"}],
             "sourceDocuments": [{"id": "doc1", "filename": "source-doc1.md",
                                  "sha256": hashlib.sha256(source).hexdigest(),
                                  "status": "candidate"}],
             "verificationTasks": []}
    return import_graph(root, json.dumps(graph).encode(), {"source-doc1.md": source})["graph_sha256"]


class AgentPathTests(unittest.TestCase):
    def test_ollama_native_combined_tools_and_finish_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_fixture(root)
            report = root / "report.json"
            report.write_text("{}")

            def load(_endpoint: str, path: Path, question: str) -> dict:
                return {"schema_version": MCP_VERSION, "report_path": str(path.resolve()),
                        "question": question, "report_sha256": "c" * 64,
                        "project_status": "passed", "facts": [], "boundary": "Static only"}

            client = NativeScriptedClient([
                ("project_evidence", {"query": "project status"}),
                ("graph_search", {"query": "CanIf 0x22"}),
                ("finish", {"answer": "项目事实与图谱候选分开。"}),
            ])
            trace = run_readonly_agent(root, goal="联合核对", model="qwen3.5:2b",
                                       provider="ollama", ollama_url="http://127.0.0.1:11434",
                                       report=report, mcp_url="http://127.0.0.1:8768/mcp",
                                       client=client, project_loader=load)
            self.assertEqual(trace["status"], "completed_unassessed")
            self.assertEqual(trace["protocol"], "ollama_native_host_bound")
            self.assertEqual(trace["citation_origin"], "host_observation_inventory")
            self.assertEqual([item["tool"] for item in trace["observations"]],
                             ["project_evidence", "graph_search"])
            self.assertEqual(trace["events"][-1]["action"]["evidence_ids"], ["o1", "o2"])
            self.assertEqual(trace["usage"]["model_calls"], 3)
            self.assertTrue(verify_trace(trace))

    def test_ollama_native_unknown_or_extra_arguments_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_fixture(root)
            for name, arguments in (("project_evidence", {"query": "status"}),
                                    ("graph_search", {"query": "CanIf", "extra": True}),
                                    ("graph_search", {"query": ""})):
                with self.subTest(name=name, arguments=arguments):
                    client = NativeScriptedClient([(name, arguments)])
                    trace = run_readonly_agent(root, goal="核对 CanIf", model="qwen3.5:2b",
                                               provider="ollama", ollama_url="http://127.0.0.1:11434",
                                               client=client)
                    self.assertEqual(trace["status"], "refused")
                    self.assertEqual(trace["observations"], [])
                    self.assertTrue(verify_trace(trace))

    def test_graph_only_uses_bound_candidate_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = graph_fixture(root)
            client = ScriptedClient([action("graph_search", query="CanIf 0x22"),
                                     action("finish", answer="候选片段指出 CanIf 不解析 0x22。", ids=["o1"])])
            trace = run_readonly_agent(root, goal="CanIf 是否解析 0x22？", model="deepseek-flash",
                                       provider="deepseek", ollama_url="", client=client)
            self.assertEqual(trace["status"], "completed_unassessed")
            self.assertTrue(verify_trace(trace))
            self.assertEqual(trace["binding"]["graph_sha256"], expected)
            self.assertEqual(trace["observations"][0]["result"]["sources"][0]["chunk_id"], "T001")
            self.assertEqual(trace["observations"][0]["result"]["sources"][0]["authority"], "candidate")
            self.assertEqual(trace["usage"]["model_calls"], 2)
            self.assertEqual(trace["usage"]["tool_calls"], 1)
            self.assertNotIn("project_evidence", client.requests[0]["messages"][1]["content"])

    def test_combined_tools_are_model_selected_and_project_is_mcp_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_fixture(root)
            report = root / "report.json"
            report.write_text("{}")
            calls: list[tuple[str, Path, str]] = []

            def load(endpoint: str, path: Path, question: str) -> dict:
                calls.append((endpoint, path, question))
                return {"schema_version": MCP_VERSION, "report_path": str(path.resolve()),
                        "question": question, "report_sha256": "a" * 64,
                        "project_status": "passed", "facts": [{"pointer": "/status", "value": "passed"}],
                        "available_fact_count": 1, "boundary": "Static only"}

            client = ScriptedClient([action("project_evidence", query="COMMUNICATION status"),
                                     action("graph_search", query="CanIf 0x22"),
                                     action("finish", answer="项目 passed；图谱只是候选。", ids=["o1", "o2"])])
            trace = run_readonly_agent(root, goal="联合核对", model="deepseek-flash", provider="deepseek",
                                       ollama_url="", report=report,
                                       mcp_url="http://127.0.0.1:8768/mcp", client=client,
                                       project_loader=load)
            self.assertEqual(trace["status"], "completed_unassessed")
            self.assertTrue(verify_trace(trace))
            self.assertEqual([item["tool"] for item in trace["observations"]],
                             ["project_evidence", "graph_search"])
            self.assertEqual(calls, [("http://127.0.0.1:8768/mcp", report, "COMMUNICATION status")])
            self.assertEqual(trace["observations"][0]["result"]["project_status"], "passed")

    def test_project_only_exposes_no_graph_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.json"
            report.write_text("{}")

            def load(_endpoint: str, path: Path, question: str) -> dict:
                return {"schema_version": MCP_VERSION, "report_path": str(path.resolve()),
                        "question": question, "report_sha256": "b" * 64,
                        "project_status": "passed", "facts": [], "boundary": "Static only"}

            client = ScriptedClient([action("project_evidence", query="status"),
                                     action("finish", answer="项目状态 passed。", ids=["o1"])])
            trace = run_readonly_agent(root, goal="核对项目状态", model="qwen3.5:2b",
                                       provider="ollama", ollama_url="http://127.0.0.1:11434",
                                       report=report, mcp_url="http://127.0.0.1:8768/mcp",
                                       client=client, project_loader=load)
            self.assertEqual(trace["status"], "completed_unassessed")
            self.assertTrue(verify_trace(trace))
            self.assertEqual(client.requests[0]["format"]["properties"]["action"]["enum"],
                             ["project_evidence", "finish", "decline"])

    def test_unavailable_tool_and_fabricated_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_fixture(root)
            for scripted in ([action("project_evidence", query="anything")],
                             [action("finish", answer="虚构结果", ids=["o1"])],
                             [action("graph_search", query="CanIf"),
                              action("finish", answer="结果", ids=["o2"])],
                             [action("graph_search", query="CanIf"),
                              action("graph_search", query="CanIf")]):
                with self.subTest(scripted=scripted):
                    trace = run_readonly_agent(root, goal="核对", model="deepseek-flash",
                                               provider="deepseek", ollama_url="",
                                               client=ScriptedClient(scripted))
                    self.assertEqual(trace["status"], "refused")
                    self.assertEqual(trace["answer"], "")
                    self.assertTrue(verify_trace(trace))

    def test_mcp_failure_and_trace_tamper_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.json"
            report.write_text("{}")

            def unavailable(_endpoint: str, _path: Path, _question: str) -> dict:
                raise ValueError("MCP unavailable")

            trace = run_readonly_agent(root, goal="项目状态", model="deepseek-flash",
                                       provider="deepseek", ollama_url="", report=report,
                                       mcp_url="http://127.0.0.1:8768/mcp",
                                       client=ScriptedClient([action("project_evidence", query="status")]),
                                       project_loader=unavailable)
            self.assertEqual(trace["status"], "blocked")
            self.assertEqual(trace["usage"]["tool_calls"], 1)
            self.assertTrue(verify_trace(trace))
            trace["events"][0]["request"]["model"] = "tampered"
            with self.assertRaisesRegex(ValueError, "Agent trace changed"):
                verify_trace(trace)

    def test_web_agent_route_saves_trace_and_session_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_fixture(root)
            server = WorkspaceServer(("127.0.0.1", 0), root, "fake:2b",
                                     "http://127.0.0.1:11434")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            def post(path: str, value: dict) -> dict:
                raw = json.dumps(value).encode()
                request = Request(base + path, data=raw, headers={
                    "Content-Type": "application/json", "X-Workbench-Token": server.token})
                return json.load(urlopen(request, timeout=10))

            try:
                session = post("/api/session", {})["session_id"]
                client = ScriptedClient([action("graph_search", query="CanIf"),
                                         action("finish", answer="图谱候选说明边界。", ids=["o1"])])
                with patch("automotive_workbench.ai_platform_agent.OllamaModelClient",
                           return_value=client):
                    result = post("/api/agent/run", {"session_id": session,
                                                      "goal": "核对 CanIf", "report": ""})
                self.assertEqual(result["status"], "completed_unassessed")
                trace_path = root / "runs" / f"{result['trace_id']}.json"
                self.assertTrue(verify_trace(json.loads(trace_path.read_text(encoding="utf-8"))))
                state = json.load(urlopen(base + f"/api/state?session={session}", timeout=10))
                self.assertEqual(state["messages"][-1]["detail"]["mode"], "agent")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
