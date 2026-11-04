from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from automotive_workbench.ai_chat import ask_general
from automotive_workbench.explanation_services import ServiceError
from automotive_workbench.knowledge_chat import forget, history, new_session, remember
from automotive_workbench.knowledge_chat_server import WorkspaceServer


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
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
