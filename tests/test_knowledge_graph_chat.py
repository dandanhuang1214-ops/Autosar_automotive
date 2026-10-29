from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from automotive_workbench.knowledge_chat import (
    ask, edit_memory, forget, history, memories, new_session, remember,
)
from automotive_workbench.knowledge_graph_workspace import (
    active_reviews, active_snapshot, import_graph, import_reviews, search_graph,
    validate_graph,
)
from automotive_workbench.knowledge_chat_server import WorkspaceServer


def fixture() -> tuple[bytes, dict[str, bytes]]:
    source = b"# Evidence\nA candidate explanation.\n"
    graph = {
        "schemaVersion": "1.0", "title": "Synthetic graph",
        "nodes": [{"id": "K001", "label": "CanIf", "summary": "Candidate only",
                   "aliases": "CAN interface", "status": "candidate",
                   "sourceDocuments": ["doc1"], "claimIds": ["C001"]}],
        "edges": [{"id": "R001", "source": "K001", "target": "K001", "type": "relates_to",
                   "sourceDocument": "doc1", "status": "candidate"}],
        "claims": [{"id": "C001", "entityIds": ["K001"],
                    "sourceChunkIds": ["T001"], "status": "candidate"}],
        "chunks": [{"id": "T001", "sourceDocument": "doc1", "entityIds": ["K001"],
                    "status": "candidate"}],
        "sourceDocuments": [{"id": "doc1", "filename": "source-doc1.md",
                             "sha256": hashlib.sha256(source).hexdigest(), "status": "candidate"}],
        "verificationTasks": [{"id": "V001", "entityIds": ["K001"], "claimIds": ["C001"]}],
    }
    return json.dumps(graph, ensure_ascii=False).encode(), {"source-doc1.md": source}


class GraphImportTest(unittest.TestCase):
    def test_real_contract_import_update_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            first = import_graph(root, raw, sources, site_version="v1")
            self.assertEqual(first["counts"]["nodes"], 1)
            self.assertEqual(active_snapshot(root)[1]["graph_sha256"], first["graph_sha256"])
            self.assertEqual(search_graph(active_snapshot(root)[0], "CanIf")["nodes"][0]["id"], "K001")
            changed = json.loads(raw)
            changed["nodes"][0]["summary"] = "A revised candidate"
            second = import_graph(root, json.dumps(changed).encode(), sources, site_version="v2")
            self.assertEqual(second["diff"]["nodes"]["changed"], ["K001"])
            self.assertEqual(second["previous_graph_sha256"], first["graph_sha256"])
            self.assertEqual(import_graph(root, json.dumps(changed).encode(), sources)["graph_sha256"], second["graph_sha256"])
            manifest = root / "snapshots" / second["graph_sha256"] / "manifest.json"
            manifest.write_text(manifest.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "manifest changed"):
                active_snapshot(root)

    def test_rejects_wrong_source_dangling_relation_and_promoted_candidate(self) -> None:
        raw, sources = fixture()
        with self.assertRaisesRegex(ValueError, "changed source document"):
            validate_graph(raw, {"source-doc1.md": b"changed"})
        graph = json.loads(raw)
        graph["edges"][0]["target"] = "missing"
        with self.assertRaisesRegex(ValueError, "dangling edge"):
            validate_graph(json.dumps(graph).encode(), sources)
        graph["edges"][0]["target"] = "K001"
        graph["nodes"][0]["status"] = "verified"
        with self.assertRaisesRegex(ValueError, "node status"):
            validate_graph(json.dumps(graph).encode(), sources)

    def test_review_export_is_version_bound_annotation_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            import_graph(root, raw, sources)
            review = {"format": "zhixing-verification-v1", "exportedAt": "2026-10-29T00:00:00Z",
                      "reviews": {"V001": {"status": "verified", "evidence": "source line 1",
                                           "note": "Reviewed separately", "updatedAt": "2026-10-29T00:00:00Z"}}}
            result = import_reviews(root, json.dumps(review).encode())
            self.assertEqual(result["status"], "user_annotation_only")
            self.assertEqual(active_reviews(root)["reviews"]["V001"]["status"], "verified")
            self.assertEqual(active_snapshot(root)[0]["nodes"][0]["status"], "candidate")
            review_file = root / "reviews" / result["graph_sha256"] / (result["review_sha256"] + ".json")
            review_file.write_text(review_file.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "Review export changed"):
                active_reviews(root)
            review_file.write_bytes(json.dumps(review).encode())
            changed = json.loads(raw)
            changed["nodes"][0]["summary"] = "New candidate version"
            import_graph(root, json.dumps(changed).encode(), sources)
            self.assertEqual(active_reviews(root)["status"], "stale_graph")
            review["reviews"]["V001"]["evidence"] = ""
            with self.assertRaisesRegex(ValueError, "invalid status or evidence"):
                import_reviews(root, json.dumps(review).encode())

    def test_memory_is_explicit_and_chat_survives_restart_without_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            import_graph(root, raw, sources)
            db = root / "chat.sqlite3"
            session = new_session(db)
            answer = ask(root, db, session_id=session, question="CanIf", report=None,
                         model="unused", ollama_url="http://127.0.0.1:11434", use_model=False)
            self.assertEqual(answer["status"], "evidence_only")
            self.assertEqual(answer["evidence"]["graph_status"], "candidate_only")
            self.assertEqual([x["role"] for x in history(db, session)], ["user", "assistant"])
            self.assertEqual(memories(db, "global"), [])
            item = remember(db, "global", "请用中文回答")
            self.assertEqual(memories(db, "global")[0]["content"], "请用中文回答")
            self.assertTrue(edit_memory(db, item["id"], "请用简洁中文回答"))
            self.assertEqual(memories(db, "global")[0]["content"], "请用简洁中文回答")
            self.assertTrue(forget(db, item["id"]))
            self.assertEqual(memories(db, "global"), [])

    def test_loopback_web_import_chat_and_token_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = WorkspaceServer(("127.0.0.1", 0), Path(directory), "unused", "http://127.0.0.1:11434")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_address[1]}"

            def post(route: str, body: dict, token: str) -> dict:
                request = Request(origin + route, json.dumps(body).encode(),
                                  {"Content-Type": "application/json", "X-Workbench-Token": token})
                with urlopen(request, timeout=5) as response:
                    return json.load(response)

            try:
                with urlopen(origin + "/", timeout=5) as response:
                    html = response.read().decode()
                self.assertIn("Automotive Workbench", html)
                self.assertIn("证据检查器", html)
                self.assertIn('role="tablist"', html)
                with self.assertRaises(HTTPError) as denied:
                    post("/api/session", {}, "wrong")
                self.assertEqual(denied.exception.code, 403)
                session = post("/api/session", {}, server.token)["session_id"]
                raw, sources = fixture()
                imported = post("/api/import", {"files": {"graph.json": raw.decode(),
                                   **{name: text.decode() for name, text in sources.items()}},
                                   "site_version": "test"}, server.token)
                self.assertEqual(imported["counts"]["nodes"], 1)
                answer = post("/api/chat", {"session_id": session, "question": "CanIf",
                                             "report": "", "use_model": False}, server.token)
                self.assertEqual(answer["evidence"]["graph_status"], "candidate_only")
                with urlopen(origin + "/api/state?session=" + session, timeout=5) as response:
                    state = json.load(response)
                self.assertEqual(len(state["messages"]), 2)
                self.assertEqual(state["sessions"][0]["title"], "CanIf")
                (Path(directory) / "active.json").write_text("{}")
                with self.assertRaises(HTTPError) as invalid:
                    urlopen(origin + "/api/state", timeout=5)
                self.assertEqual(invalid.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_model_draft_and_length_rejection_keep_evidence_separate(self) -> None:
        class FakeClient:
            records: list[dict] = []
            finish = "stop"

            def __init__(self, _endpoint):
                self.records = []

            def identity(self, _model):
                return {"digest": "a" * 64}

            def service_version(self):
                return "test"

            def complete(self, payload):
                response = {"done": True, "done_reason": self.finish,
                            "model": payload["model"], "message": {"role": "assistant", "content": "这是待核实线索。"},
                            "prompt_eval_count": 30, "eval_count": 8}
                self.records.append({"path": "/api/chat", "payload": payload,
                                     "raw": json.dumps(response)})
                return response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources = fixture()
            import_graph(root, raw, sources)
            db = root / "chat.sqlite3"
            with patch("automotive_workbench.knowledge_chat.OllamaModelClient", FakeClient):
                first = ask(root, db, session_id=new_session(db), question="CanIf",
                            report=None, model="fake", ollama_url="http://127.0.0.1:11434", use_model=True)
                self.assertEqual(first["status"], "draft_unassessed")
                self.assertEqual(first["semantic_status"], "unassessed")
                self.assertEqual(first["citations"], [])
                self.assertTrue((root / "runs" / (first["trace_id"] + ".json")).is_file())
                FakeClient.finish = "length"
                second = ask(root, db, session_id=new_session(db), question="CanIf",
                             report=None, model="fake", ollama_url="http://127.0.0.1:11434", use_model=True)
                self.assertEqual(second["status"], "model_unavailable")
                self.assertEqual(second["evidence"]["graph_status"], "candidate_only")


if __name__ == "__main__":
    unittest.main()
