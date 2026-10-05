"""Bounded read-only HTTP clients for existing local knowledge/Ollama services."""
from __future__ import annotations

import json
import math
import re
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from automotive_workbench.project_explanation import canonical, digest

MAX_RESPONSE = 2_000_000


def parse_json(raw: str) -> Any:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate JSON field")
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=pairs)
    canonical(value)
    return value


class ServiceError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Endpoint:
    def __init__(self, url: str, timeout: float):
        parts = urlsplit(url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment
                or parts.path not in ("", "/")):
            raise ValueError("Service URL must be an HTTP(S) origin without credentials")
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("Service timeout must be finite and in (0, 120] seconds")
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.records: list[dict[str, Any]] = []

    def request(self, path: str, payload: dict | None = None) -> Any:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Invalid service path")
        record: dict[str, Any] = {"path": path, "method": "POST" if payload is not None else "GET",
                                  "payload": payload, "http_status": None, "raw": "", "error": None}
        self.records.append(record)
        request = Request(self.url + path, data=canonical(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            # Explicit origins only: no environment proxy and no redirect forwarding.
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=self.timeout) as response:
                record["http_status"] = response.status
                data = response.read(MAX_RESPONSE + 1)
            record["raw"] = data[:MAX_RESPONSE].decode("utf-8", errors="replace")
            if len(data) > MAX_RESPONSE:
                raise ValueError("response_too_large")
            return parse_json(data.decode("utf-8"))
        except HTTPError as exc:
            record["http_status"] = exc.code
            record["error"] = f"http_{exc.code}"
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            record["error"] = "service_unavailable:" + type(exc).__name__
        except (ValueError, UnicodeError) as exc:
            record["error"] = "invalid_response:" + type(exc).__name__
        raise ServiceError(record["error"])


def model_identity(endpoint: Endpoint, name: str) -> dict:
    tags = endpoint.request("/api/tags")
    if not isinstance(tags, dict) or not isinstance(tags.get("models"), list):
        raise ServiceError("invalid_model_inventory")
    matches = [m for m in tags["models"] if isinstance(m, dict) and m.get("name") == name]
    if len(matches) != 1:
        raise ServiceError("model_missing_or_ambiguous")
    model = matches[0]
    if not isinstance(model.get("digest"), str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", model["digest"]):
        raise ServiceError("model_digest_missing")
    return {"name": name, "digest": model["digest"], "details": model.get("details", {})}


def retrieve(endpoint: Endpoint, query: str) -> list[dict]:
    """Consume raw search/evidence APIs; never consume repaired chat citations."""
    found = endpoint.request("/api/search", {"query": query, "limit": 3, "use_rewrite": False, "use_rerank": False})
    documents = endpoint.request("/api/documents")
    if (not isinstance(found, dict) or found.get("query") != query
            or not isinstance(found.get("results"), list) or not isinstance(documents, list)):
        raise ServiceError("invalid_knowledge_response")
    approved = {}
    for doc in documents:
        if not isinstance(doc, dict) or type(doc.get("id")) is not int or doc["id"] in approved:
            raise ServiceError("invalid_document_registry")
        approved[doc["id"]] = doc
    sources = []
    seen = set()
    for item in found["results"][:3]:
        if not isinstance(item, dict) or type(item.get("chunk_id")) is not int or type(item.get("document_id")) is not int:
            raise ServiceError("invalid_search_identity")
        if item["chunk_id"] in seen:
            raise ServiceError("duplicate_search_identity")
        seen.add(item["chunk_id"])
        doc = approved.get(item["document_id"], {})
        if (doc.get("enabled") is not True or doc.get("status") != "ready"
                or doc.get("review_status") != "approved" or doc.get("authority") not in {"official", "user_reviewed", "legacy_trusted"}
                or not isinstance(doc.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", doc["sha256"])):
            raise ServiceError("knowledge_not_approved")
        detail = endpoint.request(f"/api/evidence/{item['chunk_id']}")
        if not isinstance(detail, dict) or any(canonical(detail.get(k)) != canonical(item.get(k)) for k in ("chunk_id", "document_id", "content", "page", "title")):
            raise ServiceError("knowledge_source_drift")
        content = detail.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
            raise ServiceError("invalid_knowledge_content")
        source = {"source_kind": "manual", "document_id": doc["id"], "chunk_id": item["chunk_id"],
                  "document_sha256": doc["sha256"], "release": doc.get("release"),
                  "title": detail["title"], "page": detail["page"], "content_sha256": digest(content),
                  "excerpt": content[:1200], "authority": doc["authority"], "review_status": "approved"}
        sources.append({"source_id": digest(source), **source})
    return sources
