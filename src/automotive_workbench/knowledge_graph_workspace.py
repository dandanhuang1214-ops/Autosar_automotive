"""Versioned, local-only import of the user's independent automotive graph."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.explanation_services import parse_json
from automotive_workbench.project_explanation import canonical

SOURCE_URL = "https://automotive-knowledge-graph-oct21.silly-civet-8184.chatgpt.site/"
VERSION = "automotive-knowledge-graph-import-0.1"
MAX_GRAPH_BYTES = 5_000_000
MAX_SOURCE_BYTES = 5_000_000
MAX_REVIEW_BYTES = 1_000_000
_HASH = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.md")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ids(items: Any, kind: str) -> set[str]:
    if not isinstance(items, list) or len(items) > 100_000:
        raise ValueError(f"Invalid {kind} list")
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError(f"Invalid {kind} identity")
        identity = item["id"]
        if not identity or identity in ids:
            raise ValueError(f"Duplicate or empty {kind} identity")
        ids.add(identity)
    return ids


def validate_graph(raw: bytes, sources: dict[str, bytes]) -> dict[str, Any]:
    if not 0 < len(raw) <= MAX_GRAPH_BYTES:
        raise ValueError("Graph JSON exceeds supported size")
    graph = parse_json(raw.decode("utf-8"))
    if not isinstance(graph, dict) or graph.get("schemaVersion") != "1.0":
        raise ValueError("Unsupported graph schema")
    for key in ("nodes", "edges", "claims", "chunks", "sourceDocuments", "verificationTasks"):
        if key not in graph:
            raise ValueError(f"Missing graph {key}")
    nodes = _ids(graph["nodes"], "node")
    _ids(graph["edges"], "edge")
    claims = _ids(graph["claims"], "claim")
    chunks = _ids(graph["chunks"], "chunk")
    documents = _ids(graph["sourceDocuments"], "source document")
    _ids(graph["verificationTasks"], "verification task")
    if not nodes or not documents:
        raise ValueError("Graph needs nodes and source documents")
    for item in graph["nodes"]:
        if item.get("status") != "candidate" or not isinstance(item.get("label"), str):
            raise ValueError("Unsupported node status or label")
        if any(x not in documents for x in item.get("sourceDocuments", [])):
            raise ValueError("Node source document is missing")
        if any(x not in claims for x in item.get("claimIds", [])):
            raise ValueError("Node claim is missing")
    for item in graph["edges"]:
        if item.get("status") != "candidate" or item.get("source") not in nodes or item.get("target") not in nodes:
            raise ValueError("Unsupported or dangling edge")
        if item.get("sourceDocument") not in documents:
            raise ValueError("Edge source document is missing")
    for item in graph["claims"]:
        if item.get("status") != "candidate" or any(x not in nodes for x in item.get("entityIds", [])):
            raise ValueError("Unsupported or dangling claim")
        if any(x not in chunks for x in item.get("sourceChunkIds", [])):
            raise ValueError("Claim source chunk is missing")
    for item in graph["chunks"]:
        if item.get("status") != "candidate" or item.get("sourceDocument") not in documents:
            raise ValueError("Unsupported or dangling chunk")
        if any(x not in nodes for x in item.get("entityIds", [])):
            raise ValueError("Chunk entity is missing")
    expected_files: set[str] = set()
    for item in graph["sourceDocuments"]:
        name, expected = item.get("filename"), item.get("sha256")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or not isinstance(expected, str) or not _HASH.fullmatch(expected):
            raise ValueError("Invalid source document path or digest")
        if name in expected_files or item.get("status") != "candidate":
            raise ValueError("Duplicate or unsupported source document")
        expected_files.add(name)
        if name not in sources or not 0 < len(sources[name]) <= MAX_SOURCE_BYTES or _sha(sources[name]) != expected:
            raise ValueError("Missing or changed source document: " + name)
    if set(sources) != expected_files:
        raise ValueError("Source document set differs from graph")
    for item in graph["verificationTasks"]:
        if any(x not in nodes for x in item.get("entityIds", [])) or any(x not in claims for x in item.get("claimIds", [])):
            raise ValueError("Verification task reference is missing")
    canonical(graph)
    return graph


def _changed(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for kind in ("nodes", "edges", "claims", "chunks", "sourceDocuments", "verificationTasks"):
        old = {x["id"]: x for x in previous[kind]} if previous else {}
        new = {x["id"]: x for x in current[kind]}
        result[kind] = {
            "added": sorted(new.keys() - old.keys()),
            "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
        }
    return result


def active_snapshot(root: Path) -> tuple[dict[str, Any], dict[str, Any]] | None:
    active = root / "active.json"
    if not active.is_file() or active.is_symlink():
        return None
    pointer = parse_json(active.read_text(encoding="utf-8"))
    digest = pointer.get("graph_sha256") if isinstance(pointer, dict) else None
    manifest_hash = pointer.get("manifest_sha256") if isinstance(pointer, dict) else None
    if (not isinstance(digest, str) or not _HASH.fullmatch(digest)
            or not isinstance(manifest_hash, str) or not _HASH.fullmatch(manifest_hash)):
        raise ValueError("Invalid active graph pointer")
    folder = root / "snapshots" / digest
    manifest_raw = (folder / "manifest.json").read_bytes()
    if _sha(manifest_raw) != manifest_hash:
        raise ValueError("Graph manifest changed")
    manifest = parse_json(manifest_raw.decode("utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("graph_sha256") != digest
            or manifest.get("contract_version") != VERSION
            or not isinstance(manifest.get("source_files"), dict)
            or any(not _NAME.fullmatch(name) for name in manifest["source_files"])):
        raise ValueError("Invalid graph manifest")
    raw = (folder / "graph.json").read_bytes()
    if _sha(raw) != digest:
        raise ValueError("Active graph bytes changed")
    sources = {name: (folder / name).read_bytes() for name in manifest["source_files"]}
    graph = validate_graph(raw, sources)
    if (manifest["source_files"] != {name: _sha(data) for name, data in sorted(sources.items())}
            or manifest.get("counts") != {key: len(graph[key]) for key in ("nodes", "edges", "claims", "chunks", "verificationTasks")}):
        raise ValueError("Graph manifest inventory changed")
    return graph, manifest


def import_graph(root: Path, raw: bytes, sources: dict[str, bytes], *, site_version: str = "unreported") -> dict[str, Any]:
    graph = validate_graph(raw, sources)
    digest = _sha(raw)
    previous = active_snapshot(root)
    old_graph = previous[0] if previous else None
    diff = _changed(old_graph, graph)
    folder = root / "snapshots" / digest
    root.mkdir(parents=True, exist_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in {"graph.json": raw, **sources}.items():
        target = folder / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Existing graph snapshot changed")
        if not target.exists():
            target.write_bytes(data)
    manifest = {
        "contract_version": VERSION,
        "source_url": SOURCE_URL,
        "site_version": site_version[:80],
        "graph_sha256": digest,
        "source_files": {name: _sha(data) for name, data in sorted(sources.items())},
        "counts": {key: len(graph[key]) for key in ("nodes", "edges", "claims", "chunks", "verificationTasks")},
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "previous_graph_sha256": previous[1]["graph_sha256"] if previous else None,
        "diff": diff,
    }
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        manifest = parse_json(manifest_path.read_text(encoding="utf-8"))
    pointer = root / "active.json"
    temporary = root / "active.json.tmp"
    temporary.write_text(json.dumps({"graph_sha256": digest,
                                     "manifest_sha256": _sha(manifest_path.read_bytes())}) + "\n",
                         encoding="utf-8")
    temporary.replace(pointer)
    return manifest


def search_graph(graph: dict[str, Any], question: str, limit: int = 6) -> dict[str, Any]:
    words = [x.casefold() for x in re.findall(r"[A-Za-z][A-Za-z0-9_/-]{1,}|[\u4e00-\u9fff]{2,}", question)]
    scored = []
    for node in graph["nodes"]:
        label = str(node.get("label", "")).casefold()
        aliases = str(node.get("aliases", "")).casefold()
        score = sum(4 if word in label else 2 if word in aliases else 0 for word in words)
        if score:
            scored.append((score, node["id"], node))
    selected = [item[2] for item in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]
    ids = {item["id"] for item in selected}
    edges = [x for x in graph["edges"] if x["source"] in ids and x["target"] in ids][:24]
    return {"nodes": selected, "edges": edges, "status": "candidate_only"}


def _validate_reviews(raw: bytes, graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    if not 0 < len(raw) <= MAX_REVIEW_BYTES:
        raise ValueError("Review export exceeds supported size")
    value = parse_json(raw.decode("utf-8"))
    if (not isinstance(value, dict) or value.get("format") != "zhixing-verification-v1"
            or not isinstance(value.get("reviews"), dict)):
        raise ValueError("Unsupported review export")
    allowed = {x["id"] for x in graph["verificationTasks"]}
    counts: dict[str, int] = {x: 0 for x in ("pending", "verified", "correction", "uncertain")}
    for identity, item in value["reviews"].items():
        if identity not in allowed or not isinstance(item, dict):
            raise ValueError("Review task does not belong to active graph")
        status = item.get("status")
        if (status not in counts or not isinstance(item.get("evidence"), str)
                or not isinstance(item.get("note"), str)
                or not isinstance(item.get("updatedAt"), str)
                or (status != "pending" and not item["evidence"].strip())):
            raise ValueError("Review record has invalid status or evidence")
        counts[status] += 1
    return value, counts


def import_reviews(root: Path, raw: bytes) -> dict[str, Any]:
    """Store browser-exported task annotations without promoting graph claims."""
    active = active_snapshot(root)
    if active is None:
        raise ValueError("Import a graph before review annotations")
    graph, manifest = active
    _, counts = _validate_reviews(raw, graph)
    digest = _sha(raw)
    folder = root / "reviews" / manifest["graph_sha256"]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}.json"
    if not target.exists():
        target.write_bytes(raw)
    pointer = root / "reviews-active.json"
    temporary = root / "reviews-active.json.tmp"
    temporary.write_text(json.dumps({"graph_sha256": manifest["graph_sha256"],
                                     "review_sha256": digest}) + "\n", encoding="utf-8")
    temporary.replace(pointer)
    return {"graph_sha256": manifest["graph_sha256"], "review_sha256": digest,
            "counts": counts, "status": "user_annotation_only"}


def active_reviews(root: Path) -> dict[str, Any] | None:
    pointer = root / "reviews-active.json"
    if not pointer.is_file():
        return None
    value = parse_json(pointer.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid review pointer")
    graph_hash, review_hash = value.get("graph_sha256"), value.get("review_sha256")
    if (not isinstance(graph_hash, str) or not _HASH.fullmatch(graph_hash)
            or not isinstance(review_hash, str) or not _HASH.fullmatch(review_hash)):
        raise ValueError("Invalid review digest")
    active = active_snapshot(root)
    if active is None or active[1]["graph_sha256"] != graph_hash:
        return {"status": "stale_graph", "graph_sha256": graph_hash}
    raw = (root / "reviews" / graph_hash / f"{review_hash}.json").read_bytes()
    if _sha(raw) != review_hash:
        raise ValueError("Review export changed")
    value, _ = _validate_reviews(raw, active[0])
    return {"status": "user_annotation_only", "graph_sha256": graph_hash,
            "review_sha256": review_hash, "reviews": value["reviews"]}
