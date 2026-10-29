"""Loopback web entry for versioned graph, project evidence and local Ollama."""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from automotive_workbench.explanation_services import parse_json
from automotive_workbench.knowledge_chat import (
    _connect, ask, edit_memory, forget, history, memories, new_session, remember,
)
from automotive_workbench.knowledge_graph_workspace import (
    MAX_GRAPH_BYTES, MAX_REVIEW_BYTES, MAX_SOURCE_BYTES, active_reviews,
    active_snapshot, import_graph, import_reviews,
)

HTML = Path(__file__).with_name("knowledge_chat_ui.html").read_text(encoding="utf-8")


class WorkspaceServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], root: Path, model: str, ollama_url: str):
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("Workbench web server must bind to loopback")
        self.root = root
        self.db_path = root / "chat.sqlite3"
        self.model = model
        self.ollama_url = ollama_url
        self.token = secrets.token_urlsafe(24)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: WorkspaceServer

    def _trusted_host(self) -> bool:
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{self.server.server_address[1]}",
                        f"localhost:{self.server.server_address[1]}"}

    def _json(self, status: int, body: Mapping[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._json(403, {"error": "Local host required"})
            return
        try:
            self._get_local()
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            self._json(400, {"error": str(exc)[:500]})

    def _get_local(self) -> None:
        route = urlsplit(self.path)
        if route.path == "/":
            raw = HTML.replace("__TOKEN__", self.server.token).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if route.path == "/api/state":
            session = parse_qs(route.query).get("session", [""])[0]
            active = active_snapshot(self.server.root)
            with _connect(self.server.db_path) as db:
                rows = db.execute(
                    "SELECT s.id,s.created_at,(SELECT substr(m.content,1,70) FROM messages m "
                    "WHERE m.session_id=s.id AND m.role='user' ORDER BY m.id DESC LIMIT 1) AS title "
                    "FROM sessions s ORDER BY s.created_at DESC LIMIT 100"
                ).fetchall()
            selected = session if any(x["id"] == session for x in rows) else (rows[0]["id"] if rows else "")
            messages = history(self.server.db_path, selected) if selected else []
            latest = next((x for x in reversed(messages) if x["role"] == "assistant"), None)
            memory_scope = latest["project_sha256"] if latest else "global"
            self._json(200, {"active": active[1] if active else None,
                             "reviews": active_reviews(self.server.root),
                             "sessions": [dict(x) for x in rows],
                             "messages": messages,
                             "memories": memories(self.server.db_path, memory_scope or "global")})
            return
        if route.path == "/api/source":
            name = parse_qs(route.query).get("name", [""])[0]
            active = active_snapshot(self.server.root)
            if not active or name not in active[1]["source_files"]:
                self._json(404, {"error": "Source document not found"})
                return
            raw = (self.server.root / "snapshots" / active[1]["graph_sha256"] / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._trusted_host():
            self._json(403, {"error": "Local host required"})
            return
        if self.headers.get("X-Workbench-Token") != self.server.token:
            self._json(403, {"error": "Invalid local session token"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 15_000_000:
                raise ValueError("Request body size is invalid")
            body = parse_json(self.rfile.read(size).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            result: dict[str, Any]
            if self.path == "/api/session":
                result = {"session_id": new_session(self.server.db_path)}
            elif self.path == "/api/import":
                files = body.get("files")
                if not isinstance(files, dict) or not all(isinstance(x, str) and isinstance(v, str) for x, v in files.items()):
                    raise ValueError("Select graph.json and its source Markdown files")
                raw = files.get("graph.json", "").encode("utf-8")
                sources = {name: data.encode("utf-8") for name, data in files.items() if name != "graph.json"}
                if len(raw) > MAX_GRAPH_BYTES or any(len(x) > MAX_SOURCE_BYTES for x in sources.values()):
                    raise ValueError("Graph import exceeds supported size")
                result = import_graph(self.server.root, raw, sources,
                                      site_version=str(body.get("site_version", "unreported")))
            elif self.path == "/api/chat":
                report = body.get("report")
                result = ask(self.server.root, self.server.db_path,
                             session_id=str(body.get("session_id", "")), question=str(body.get("question", "")),
                             report=Path(report) if isinstance(report, str) and report else None,
                             model=self.server.model, ollama_url=self.server.ollama_url,
                             use_model=body.get("use_model") is True)
            elif self.path == "/api/reviews/import":
                content = body.get("content")
                if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_REVIEW_BYTES:
                    raise ValueError("Invalid review export")
                result = import_reviews(self.server.root, content.encode("utf-8"))
            elif self.path == "/api/memory":
                result = remember(self.server.db_path, str(body.get("scope", "")), str(body.get("content", "")))
            elif self.path == "/api/memory/delete":
                result = {"deleted": forget(self.server.db_path, str(body.get("id", "")))}
            elif self.path == "/api/memory/edit":
                result = {"edited": edit_memory(self.server.db_path, str(body.get("id", "")),
                                                 str(body.get("content", "")))}
            else:
                self._json(404, {"error": "Not found"})
                return
            self._json(200, result)
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            self._json(400, {"error": str(exc)[:500]})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local automotive graph and project chat")
    parser.add_argument("--data", type=Path, default=Path("output/knowledge-chat"))
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--model", default="qwen3.5:2b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    server = WorkspaceServer(("127.0.0.1", args.port), args.data, args.model, args.ollama_url)
    print(f"Automotive Workbench: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
