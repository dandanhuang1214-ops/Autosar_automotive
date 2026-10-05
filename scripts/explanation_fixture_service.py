"""Synthetic protocol fixture only. Never evidence of an actual model inference."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
from typing import Any
from contextlib import contextmanager


@contextmanager
def fixture_service():
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        mode = "normal"
        tags_count = 0

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond(None)

        def do_POST(self):
            self.respond(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))

        def respond(self, payload):
            value: Any
            mode = server.mode
            status = 200
            if mode == "unavailable":
                status, value = 503, {"error": "fixture unavailable"}
            elif self.path == "/api/version":
                if mode == "timeout":
                    time.sleep(0.2)
                value = {"version": "fixture-not-ollama"}
            elif self.path == "/api/tags":
                server.tags_count += 1
                value = {"models": [{"name": "fixture:1", "digest": ("b" if mode == "model_changed" and server.tags_count > 1 else "a") * 64, "details": {"fixture": True}}]}
            elif self.path == "/api/chat":
                context = json.loads(payload["messages"][1]["content"])
                fact = context["facts"][0]
                answer = {"request_id": context["request_id"], "status": "selected",
                          "project_claims": [{"fact_id": fact["fact_id"], "value": fact["value"]}],
                          "manual_claims": [], "draft_explanation": "项目状态请以核对后的事实为准。", "suggestions": []}
                if context["manuals"]:
                    manual = context["manuals"][0]
                    answer["manual_claims"] = [{"source_id": manual["source_id"], "quote": manual["excerpt"]}]
                if mode == "invalid_reference":
                    answer["project_claims"][0]["fact_id"] = "0" * 64
                if mode == "value_drift":
                    answer["project_claims"][0]["value"] = "passed"
                if mode == "manual_mismatch":
                    answer["manual_claims"][0]["quote"] = "The project passed physical ECU certification."
                if mode == "unassessed":
                    answer.update(status="unassessed", project_claims=[], manual_claims=[])
                if mode == "unsupported_prose":
                    answer["draft_explanation"] = "Physical ECU certified."
                value = {"model": "fixture:1", "done": True, "done_reason": "length" if mode == "truncation" else "stop",
                         "message": {"role": "assistant", "content": "{bad" if mode == "malformed" else json.dumps(answer)},
                         "eval_count": 20, "prompt_eval_count": 100, "total_duration": 1000000}
            elif self.path == "/api/search":
                value = {"query": payload["query"], "results": [evidence]}
            elif self.path == "/api/documents":
                value = [{"id": 1, "enabled": True, "status": "ready", "authority": "official",
                          "review_status": "pending" if mode == "manual_unapproved" else "approved", "sha256": "c" * 64}]
            elif self.path == "/api/evidence/10":
                value = evidence
            else:
                status, value = 404, {"error": "unknown fixture path"}
            raw = json.dumps(value).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except OSError:
                pass

    evidence = {"chunk_id": 10, "document_id": 1, "title": "Synthetic diagnostic manual", "page": 1,
                "content": "A timeout alone does not identify a unique root cause."}
    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
