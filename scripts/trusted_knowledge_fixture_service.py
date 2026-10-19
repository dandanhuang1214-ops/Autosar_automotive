"""Serve a frozen, reviewed official-knowledge corpus over the read-only API."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from typing import Any, Iterator
from urllib.parse import urlsplit

from automotive_workbench.project_explanation import canonical, digest, read


CORPUS_VERSION = "agent-reviewed-knowledge-corpus-0.1"
_FIELDS = {"corpus_id", "schema_version", "documents", "boundary"}
_DOCUMENT_FIELDS = {
    "document_id",
    "document_sha256",
    "authority",
    "release",
    "title",
    "source_url",
    "retrieved_at",
    "chunks",
}
_CHUNK_FIELDS = {"chunk_id", "page", "content"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def document_body(document: dict[str, Any]) -> dict[str, Any]:
    """Return the complete official-source record covered by its digest."""
    return {
        name: document.get(name)
        for name in (
            "document_id",
            "authority",
            "release",
            "title",
            "source_url",
            "retrieved_at",
            "chunks",
        )
    }


def corpus_body(corpus: dict[str, Any]) -> dict[str, Any]:
    """Return all corpus content covered by corpus_id."""
    return {
        "schema_version": corpus.get("schema_version"),
        "documents": corpus.get("documents"),
        "boundary": corpus.get("boundary"),
    }


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_corpus(value: Any) -> dict[str, Any]:
    """Validate identities, official locators, and closed corpus structure."""
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("Invalid reviewed knowledge corpus fields")
    if value["schema_version"] != CORPUS_VERSION:
        raise ValueError("Unsupported reviewed knowledge corpus version")
    if not isinstance(value["boundary"], str) or not value["boundary"].strip():
        raise ValueError("Reviewed knowledge corpus requires a boundary")
    documents = value["documents"]
    if not isinstance(documents, list) or not documents:
        raise ValueError("Reviewed knowledge corpus requires documents")

    document_ids: set[int] = set()
    chunk_ids: set[int] = set()
    for document in documents:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ValueError("Invalid reviewed knowledge document fields")
        document_id = document["document_id"]
        if type(document_id) is not int or document_id < 1 or document_id in document_ids:
            raise ValueError("Reviewed knowledge document IDs must be unique positive integers")
        document_ids.add(document_id)
        if document["authority"] != "official":
            raise ValueError("Reviewed knowledge corpus accepts official sources only")
        if any(
            not isinstance(document[name], str) or not document[name].strip()
            for name in ("release", "title", "source_url")
        ):
            raise ValueError("Reviewed knowledge document metadata is invalid")
        source = urlsplit(document["source_url"])
        if (
            source.scheme != "https"
            or source.hostname != "help.vector.com"
            or source.username
            or source.password
            or source.fragment
        ):
            raise ValueError("Reviewed knowledge source must be an official Vector HTTPS URL")
        if not _timestamp(document["retrieved_at"]):
            raise ValueError("Reviewed knowledge retrieval timestamp is invalid")
        chunks = document["chunks"]
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("Reviewed knowledge document requires chunks")
        for chunk in chunks:
            if not isinstance(chunk, dict) or set(chunk) != _CHUNK_FIELDS:
                raise ValueError("Invalid reviewed knowledge chunk fields")
            chunk_id = chunk["chunk_id"]
            page = chunk["page"]
            content = chunk["content"]
            if type(chunk_id) is not int or chunk_id < 1 or chunk_id in chunk_ids:
                raise ValueError("Reviewed knowledge chunk IDs must be unique positive integers")
            chunk_ids.add(chunk_id)
            if page is not None and (type(page) is not int or page < 1):
                raise ValueError("Reviewed knowledge page must be null or a positive integer")
            if not isinstance(content, str) or not 0 < len(content.strip()) <= 1200:
                raise ValueError("Reviewed knowledge chunk content must contain 1..1200 characters")
        if (
            not isinstance(document["document_sha256"], str)
            or not _SHA256.fullmatch(document["document_sha256"])
            or document["document_sha256"] != digest(document_body(document))
        ):
            raise ValueError("Reviewed knowledge document digest does not bind content")

    if (
        not isinstance(value["corpus_id"], str)
        or not _SHA256.fullmatch(value["corpus_id"])
        or value["corpus_id"] != digest(corpus_body(value))
    ):
        raise ValueError("Reviewed knowledge corpus ID does not bind content")
    return json.loads(canonical(value))


def load_corpus(path: Path) -> dict[str, Any]:
    """Load a corpus with duplicate-key and canonical-number checks."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Reviewed knowledge corpus must be a regular non-symlink file")
    return validate_corpus(read(path))


@contextmanager
def trusted_knowledge_service(
    corpus_path: Path,
) -> Iterator[tuple[ThreadingHTTPServer, str]]:
    """Expose the entire tiny frozen corpus; this is not a retrieval-quality test."""
    corpus = load_corpus(corpus_path)
    documents = corpus["documents"]
    details = {
        chunk["chunk_id"]: {
            "chunk_id": chunk["chunk_id"],
            "document_id": document["document_id"],
            "title": document["title"],
            "page": chunk["page"],
            "content": chunk["content"],
        }
        for document in documents
        for chunk in document["chunks"]
    }

    class Server(ThreadingHTTPServer):
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, status: int, value: Any) -> None:
            raw = canonical(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path == "/api/documents":
                self._send(
                    200,
                    [
                        {
                            "id": item["document_id"],
                            "enabled": True,
                            "status": "ready",
                            "authority": "official",
                            "review_status": "approved",
                            "sha256": item["document_sha256"],
                            "release": item["release"],
                        }
                        for item in documents
                    ],
                )
                return
            match = re.fullmatch(r"/api/evidence/([1-9][0-9]*)", self.path)
            if match is not None and int(match.group(1)) in details:
                self._send(200, details[int(match.group(1))])
                return
            self._send(404, {"error": "unknown fixture path"})

        def do_POST(self) -> None:
            if self.path != "/api/search":
                self._send(404, {"error": "unknown fixture path"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
            except (TypeError, ValueError, json.JSONDecodeError):
                self._send(400, {"error": "invalid request"})
                return
            if (
                not isinstance(payload, dict)
                or set(payload)
                != {"query", "limit", "use_rewrite", "use_rerank"}
                or not isinstance(payload["query"], str)
                or not payload["query"]
                or payload["limit"] != 3
                or payload["use_rewrite"] is not False
                or payload["use_rerank"] is not False
            ):
                self._send(400, {"error": "invalid bounded search"})
                return
            self._send(
                200,
                {
                    "query": payload["query"],
                    "results": list(details.values())[:3],
                },
            )

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
