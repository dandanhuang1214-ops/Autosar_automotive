"""Fetch the owner's static automotive graph into the verified local snapshot store."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

from automotive_workbench.knowledge_graph_workspace import (
    MAX_GRAPH_BYTES, MAX_SOURCE_BYTES, SOURCE_URL, active_snapshot, import_graph,
    validate_graph,
)

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.md")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _fetch(name: str, token: str, limit: int) -> bytes:
    if name != "graph.json" and not _NAME.fullmatch(name):
        raise ValueError("Invalid graph Site file name")
    request = Request(SOURCE_URL + name, headers={
        "OAI-Sites-Authorization": "Bearer " + token,
        "Accept": "application/json" if name == "graph.json" else "text/plain",
    })
    with build_opener(_NoRedirect).open(request, timeout=30) as response:
        if response.status != 200 or response.url != SOURCE_URL + name:
            raise ValueError("Unexpected graph Site response")
        raw = response.read(limit + 1)
    if not 0 < len(raw) <= limit:
        raise ValueError("Graph Site file exceeds supported size")
    return raw


def sync_site_graph(root: Path, token: str) -> dict:
    """Switch the active graph only after all Site files pass import validation."""
    if not token or any(ch in token for ch in "\r\n"):
        raise ValueError("Graph Site access token is required")
    raw = _fetch("graph.json", token, MAX_GRAPH_BYTES)
    graph = json.loads(raw.decode("utf-8"))
    if not isinstance(graph, dict) or not isinstance(graph.get("sourceDocuments"), list):
        raise ValueError("Invalid graph Site document list")
    names = [item.get("filename") for item in graph["sourceDocuments"] if isinstance(item, dict)]
    if len(names) != len(graph["sourceDocuments"]) or len(names) > 100:
        raise ValueError("Invalid graph Site document list")
    if any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in names):
        raise ValueError("Invalid graph Site source file name")
    sources = {name: _fetch(name, token, MAX_SOURCE_BYTES) for name in names}
    validate_graph(raw, sources)
    current = active_snapshot(root)
    if current and current[1]["graph_sha256"] == hashlib.sha256(raw).hexdigest():
        return current[1]
    return import_graph(root, raw, sources, site_version="site-live")
