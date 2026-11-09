from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automotive_workbench.ai_chat import ask_general, ask_general_stream
from automotive_workbench.deepseek_chat import DeepSeekChatClient
from automotive_workbench.explanation_services import ServiceError
from automotive_workbench.knowledge_chat import new_session
from automotive_workbench.knowledge_chat_server import WorkspaceServer


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, response: bytes):
        self.response = response
        self.request = None

    def open(self, request, timeout):
        self.request = request
        return Response(self.response)


class DeepSeekTransportTest(unittest.TestCase):
    def test_completion_normalizes_usage_without_recording_key(self) -> None:
        raw = json.dumps({"id": "chat-1", "model": "deepseek-flash", "choices": [{
            "message": {"role": "assistant", "content": "有据回答。"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4}}).encode()
        opener = Opener(raw)
        with patch("automotive_workbench.deepseek_chat.build_opener", return_value=opener):
            client = DeepSeekChatClient("test-secret")
            result = client.complete({"model": "deepseek-flash", "messages": [
                {"role": "user", "content": "问题"}], "stream": False})
        self.assertEqual(result["message"]["content"], "有据回答。")
        self.assertEqual(result["prompt_eval_count"], 12)
        self.assertEqual(result["eval_count"], 4)
        self.assertEqual(result["response_id"], "chat-1")
        sent = json.loads(opener.request.data)
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertEqual(sent["model"], "deepseek-flash")
        self.assertNotIn("test-secret", json.dumps(client.records))

    def test_stream_requires_done_and_preserves_usage(self) -> None:
        def event(choices, usage=None):
            return ("data: " + json.dumps({"id": "chat-2", "model": "deepseek-flash",
                                              "choices": choices, "usage": usage}) + "\n\n").encode()

        chunks = (event([{"delta": {"content": "你好"}, "finish_reason": None}])
                  + event([{"delta": {"content": "。"}, "finish_reason": "stop"}])
                  + event([], {"prompt_tokens": 9, "completion_tokens": 2})
                  + b"data: [DONE]\n\n")
        opener = Opener(chunks)
        with patch("automotive_workbench.deepseek_chat.build_opener", return_value=opener):
            client = DeepSeekChatClient("test-secret")
            frames = list(client.stream({"model": "deepseek-flash", "messages": [], "stream": True}))
        self.assertEqual([frame["message"]["content"] for frame in frames], ["你好", "。", ""])
        self.assertEqual(frames[-1]["done_reason"], "stop")
        self.assertEqual(frames[-1]["eval_count"], 2)
        self.assertTrue(json.loads(opener.request.data)["stream_options"]["include_usage"])

        with patch("automotive_workbench.deepseek_chat.build_opener",
                   return_value=Opener(chunks.replace(b"data: [DONE]\n\n", b""))):
            with self.assertRaisesRegex(ServiceError, "incomplete_deepseek_stream"):
                list(DeepSeekChatClient("test-secret").stream({
                    "model": "deepseek-flash", "messages": [], "stream": True}))


class StubDeepSeek:
    def __init__(self, api_key):
        assert api_key == "test-secret"
        self.records = []

    def complete(self, payload):
        return self._frame(payload, "云端回答。")

    def stream(self, payload):
        yield {"model": payload["model"], "message": {"role": "assistant", "content": "云端"},
               "done": False}
        yield self._frame(payload, "")

    @staticmethod
    def _frame(payload, content):
        return {"model": payload["model"], "reported_model": "deepseek-flash",
                "response_id": "chat-3", "message": {"role": "assistant", "content": content},
                "done": True, "done_reason": "stop", "prompt_eval_count": 8,
                "eval_count": 3}

    def cancel_stream(self):
        pass


class DeepSeekChatIntegrationTest(unittest.TestCase):
    def test_deepseek_server_requires_key_before_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY is required"):
                WorkspaceServer(("127.0.0.1", 0), Path(directory), "deepseek-flash",
                                "http://127.0.0.1:11434", provider="deepseek")

    def test_both_chat_paths_use_deepseek_without_ollama_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "chat.sqlite3"
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-secret"}), \
                 patch("automotive_workbench.ai_chat.DeepSeekChatClient", StubDeepSeek):
                full = ask_general(root, db, session_id=new_session(db), question="第一题",
                                   model="deepseek-flash", ollama_url="http://127.0.0.1:11434",
                                   provider="deepseek")
                streamed = ask_general_stream(
                    root, db, session_id=new_session(db), question="第二题",
                    model="deepseek-flash", ollama_url="http://127.0.0.1:11434",
                    provider="deepseek", emit=lambda _kind, _payload: None,
                    cancelled=lambda: False, register_client=lambda _client: None)
            self.assertEqual((full["status"], streamed["status"]), ("answered", "answered"))
            self.assertEqual(streamed["answer"], "云端")
            self.assertIsNone(full["model"]["digest"])
            self.assertEqual(full["model"]["provider"], "deepseek")
            self.assertEqual(full["model"]["response_id"], "chat-3")
