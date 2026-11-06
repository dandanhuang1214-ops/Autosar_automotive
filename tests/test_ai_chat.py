from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from automotive_workbench.ai_chat import ask_general, ask_general_stream
from automotive_workbench.explanation_services import ServiceError
from automotive_workbench.knowledge_chat import forget, history, new_session, remember
from automotive_workbench.knowledge_chat_server import WorkspaceServer
from automotive_workbench.knowledge_graph_workspace import import_graph
from tests.test_knowledge_graph_chat import fixture


class FakeClient:
    calls: list[dict] = []
    fail = False

    def __init__(self, _endpoint):
        self.records = []

    def identity(self, _model):
        if self.fail:
            raise ServiceError("service_unavailable:URLError")
        return {"digest": "a" * 64}

    def service_version(self):
        return "test"

    def complete(self, payload):
        self.calls.append(payload)
        response = {"done": True, "done_reason": "stop", "model": payload["model"],
                    "message": {"role": "assistant", "content": "这是直接回答。"},
                    "total_duration": 1_500_000_000, "load_duration": 100_000_000,
                    "prompt_eval_duration": 200_000_000, "eval_duration": 1_200_000_000,
                    "prompt_eval_count": 20, "eval_count": 7}
        self.records.append({"path": "/api/chat", "payload": payload})
        return response

    def stream(self, payload):
        self.calls.append(payload)
        self.records.append({"path": "/api/chat", "payload": payload})
        yield {"model": payload["model"], "message": {"role": "assistant", "content": "这是"}, "done": False}
        yield {"model": payload["model"], "message": {"role": "assistant", "content": "流式回答。"}, "done": False}
        yield {"model": payload["model"], "message": {"role": "assistant", "content": ""},
               "done": True, "done_reason": "stop", "eval_count": 6}

    def cancel_stream(self):
        pass


class DirectChatTest(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []
        FakeClient.fail = False

    def test_no_evidence_multiturn_and_call_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            first_session = new_session(db)
            with patch("automotive_workbench.ai_chat.OllamaModelClient", FakeClient):
                first = ask_general(root, db, session_id=first_session, question="你好",
                                    model="fake:2b", ollama_url="http://127.0.0.1:11434")
                second = ask_general(root, db, session_id=first_session, question="继续说",
                                     model="fake:2b", ollama_url="http://127.0.0.1:11434")
                other = ask_general(root, db, session_id=new_session(db), question="新会话",
                                    model="fake:2b", ollama_url="http://127.0.0.1:11434")
            self.assertEqual(first["status"], "answered")
            self.assertEqual(first["answer"], "这是直接回答。")
            self.assertTrue(first["called_at"].endswith("+00:00"))
            self.assertIsInstance(first["elapsed_ms"], float)
            self.assertEqual(first["timings_ms"]["total_duration"], 1500)
            self.assertEqual(second["model"]["name"], "fake:2b")
            self.assertEqual([m["role"] for m in FakeClient.calls[1]["messages"]],
                             ["system", "user", "assistant", "user"])
            self.assertEqual(len(FakeClient.calls[2]["messages"]), 2)
            self.assertEqual(other["status"], "answered")
            self.assertEqual([m["role"] for m in history(db, first_session)],
                             ["user", "assistant", "user", "assistant"])
            trace = json.loads((root / "runs" / f"{first['trace_id']}.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["result"]["called_at"], first["called_at"])

    def test_offline_answer_is_not_replayed_as_model_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            session = new_session(db)
            with patch("automotive_workbench.ai_chat.OllamaModelClient", FakeClient):
                FakeClient.fail = True
                offline = ask_general(root, db, session_id=session, question="失败的问题",
                                      model="fake:2b", ollama_url="http://127.0.0.1:11434")
                FakeClient.fail = False
                recovered = ask_general(root, db, session_id=session, question="重试",
                                        model="fake:2b", ollama_url="http://127.0.0.1:11434")
            self.assertEqual(offline["status"], "model_unavailable")
            self.assertTrue(offline["model_attempted"])
            self.assertEqual(recovered["status"], "answered")
            self.assertEqual(len(FakeClient.calls[0]["messages"]), 2)

    def test_stream_and_cancel_keep_partial_out_of_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            session = new_session(db)
            events = []
            stopped = threading.Event()

            def emit(kind, payload):
                events.append((kind, payload))
                if kind == "delta" and payload["content"] == "这是":
                    stopped.set()

            with patch("automotive_workbench.ai_chat.StreamingChatClient", FakeClient):
                partial = ask_general_stream(
                    root, db, session_id=session, question="第一题", model="fake:2b",
                    ollama_url="http://127.0.0.1:11434", emit=emit,
                    cancelled=stopped.is_set, register_client=lambda _client: None)
                stopped.clear()
                complete = ask_general_stream(
                    root, db, session_id=session, question="第二题", model="fake:2b",
                    ollama_url="http://127.0.0.1:11434",
                    emit=lambda kind, payload: events.append((kind, payload)),
                    cancelled=stopped.is_set, register_client=lambda _client: None)
            self.assertTrue(FakeClient.calls[0]["stream"])
            self.assertEqual(partial["status"], "cancelled")
            self.assertEqual(partial["answer"], "这是")
            self.assertEqual(complete["status"], "answered")
            self.assertEqual(complete["answer"], "这是流式回答。")
            self.assertEqual(len(FakeClient.calls[1]["messages"]), 2)
            self.assertEqual([kind for kind, _ in events].count("done"), 2)
            self.assertEqual([m["detail"]["status"] for m in history(db, session)
                              if m["role"] == "assistant"], ["cancelled", "answered"])

    def test_explicit_memory_crosses_sessions_and_can_be_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            saved = remember(db, "global", "请用简洁中文回答")
            with patch("automotive_workbench.ai_chat.OllamaModelClient", FakeClient):
                first = ask_general(root, db, session_id=new_session(db), question="你好",
                                    model="fake:2b", ollama_url="http://127.0.0.1:11434")
                self.assertTrue(forget(db, saved["id"]))
                second = ask_general(root, db, session_id=new_session(db), question="你好",
                                     model="fake:2b", ollama_url="http://127.0.0.1:11434")
            self.assertEqual(first["memory_count"], 1)
            self.assertIn("请用简洁中文回答", FakeClient.calls[0]["messages"][1]["content"])
            self.assertEqual(second["memory_count"], 0)
            self.assertEqual(len(FakeClient.calls[1]["messages"]), 2)

    def test_existing_knowledge_service_is_searched_without_source_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            session = new_session(db)
            source = {"source_id": "s1", "title": "CAN 手册", "document_id": 4,
                      "chunk_id": 7, "page": 2, "document_sha256": "a" * 64,
                      "authority": "user_reviewed", "excerpt": "CAN 是通信总线。"}
            with patch("automotive_workbench.ai_chat.StreamingChatClient", FakeClient), \
                    patch("automotive_workbench.ai_chat.retrieve", return_value=[source]) as search:
                result = ask_general_stream(
                    root, db, session_id=session, question="CAN 是什么", model="fake:2b",
                    ollama_url="http://127.0.0.1:11434",
                    knowledge_url="http://127.0.0.1:18080",
                    emit=lambda _kind, _payload: None, cancelled=lambda: False,
                    register_client=lambda _client: None)
            search.assert_called_once()
            self.assertEqual(result["knowledge"]["status"], "retrieved")
            self.assertEqual(result["knowledge"]["sources"][0]["chunk_id"], 7)
            self.assertTrue(any("CAN 手册" in item["content"]
                                for item in FakeClient.calls[0]["messages"]))

    def test_active_graph_is_searched_automatically_as_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            manifest = import_graph(root, raw, sources, site_version="site-live")
            db = root / "chat.sqlite3"
            with patch("automotive_workbench.ai_chat.StreamingChatClient", FakeClient):
                result = ask_general_stream(
                    root, db, session_id=new_session(db), question="CanIf 是什么",
                    model="fake:2b", ollama_url="http://127.0.0.1:11434",
                    emit=lambda _kind, _payload: None, cancelled=lambda: False,
                    register_client=lambda _client: None)
            self.assertEqual(result["knowledge"]["status"], "graph_candidates")
            self.assertEqual(result["knowledge"]["graph_sha256"], manifest["graph_sha256"])
            self.assertEqual(result["knowledge"]["sources"][0]["authority"], "candidate")
            self.assertEqual(result["knowledge"]["sources"][0]["filename"], "source-doc1.md")
            self.assertTrue(any("尚未独立核实" in item["content"]
                                for item in FakeClient.calls[0]["messages"]))

    def test_active_graph_no_match_keeps_direct_chat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            import_graph(root, raw, sources)
            with patch("automotive_workbench.ai_chat.OllamaModelClient", FakeClient):
                result = ask_general(root, root / "chat.sqlite3",
                                     session_id=new_session(root / "chat.sqlite3"),
                                     question="你好", model="fake:2b",
                                     ollama_url="http://127.0.0.1:11434")
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["knowledge"]["status"], "graph_no_match")

    def test_knowledge_outage_is_visible_and_direct_chat_continues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            with patch("automotive_workbench.ai_chat.StreamingChatClient", FakeClient), \
                    patch("automotive_workbench.ai_chat.retrieve",
                          side_effect=ServiceError("service_unavailable:URLError")):
                result = ask_general_stream(
                    root, db, session_id=new_session(db), question="你好",
                    model="fake:2b", ollama_url="http://127.0.0.1:11434",
                    knowledge_url="http://127.0.0.1:18080",
                    emit=lambda _kind, _payload: None, cancelled=lambda: False,
                    register_client=lambda _client: None)
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["knowledge"]["status"], "unavailable")
            self.assertEqual(result["knowledge"]["sources"], [])

    def test_web_direct_chat_without_graph_or_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = WorkspaceServer(("127.0.0.1", 0), Path(directory), "fake:2b",
                                     "http://127.0.0.1:11434")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_address[1]}"

            def post(route: str, body: dict) -> dict:
                request = Request(origin + route, json.dumps(body).encode(),
                                  {"Content-Type": "application/json",
                                   "X-Workbench-Token": server.token})
                with urlopen(request, timeout=5) as response:
                    return json.load(response)

            try:
                with patch("automotive_workbench.ai_chat.OllamaModelClient", FakeClient):
                    session = post("/api/session", {})["session_id"]
                    answer = post("/api/chat", {"mode": "general", "session_id": session,
                                                "question": "你好"})
                self.assertEqual(answer["status"], "answered")
                self.assertEqual(answer["model"]["name"], "fake:2b")
                with urlopen(origin + "/api/state?session=" + session) as response:
                    state = json.load(response)
                self.assertEqual(state["messages"][-1]["detail"]["mode"], "general")
                with patch("automotive_workbench.ai_chat.StreamingChatClient", FakeClient):
                    request = Request(origin + "/api/chat/stream", json.dumps({
                        "mode": "general", "session_id": session,
                        "question": "流式题", "request_id": str(uuid.uuid4()),
                    }).encode(), {"Content-Type": "application/json",
                                 "X-Workbench-Token": server.token})
                    with urlopen(request, timeout=5) as response:
                        events = [json.loads(line) for line in response]
                self.assertEqual([event["type"] for event in events],
                                 ["start", "delta", "delta", "done"])
                self.assertEqual(events[-1]["status"], "answered")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
