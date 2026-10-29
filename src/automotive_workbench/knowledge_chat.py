"""Local-only graph and project evidence chat with explicit durable memory."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.explanation_services import Endpoint, ServiceError, parse_json
from automotive_workbench.knowledge_graph_workspace import active_reviews, active_snapshot, search_graph
from automotive_workbench.model_client import OllamaModelClient
from automotive_workbench.project_explanation import build_request, canonical


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL,
          content TEXT NOT NULL, graph_sha256 TEXT NOT NULL, project_sha256 TEXT,
          detail_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories (
          id TEXT PRIMARY KEY, scope TEXT NOT NULL, content TEXT NOT NULL,
          source_message_id INTEGER, created_at TEXT NOT NULL);
    """)
    try:
        with db:
            yield db
    finally:
        db.close()


def new_session(db_path: Path) -> str:
    identity = uuid.uuid4().hex
    with _connect(db_path) as db:
        db.execute("INSERT INTO sessions VALUES (?,?)", (identity, _now()))
    return identity


def history(db_path: Path, session_id: str) -> list[dict[str, Any]]:
    with _connect(db_path) as db:
        rows = db.execute(
            "SELECT id,role,content,graph_sha256,project_sha256,detail_json,created_at "
            "FROM messages WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
    return [{**dict(row), "detail": parse_json(row["detail_json"])} for row in rows]


def memories(db_path: Path, scope: str) -> list[dict[str, Any]]:
    with _connect(db_path) as db:
        rows = db.execute(
            "SELECT id,scope,content,source_message_id,created_at FROM memories "
            "WHERE scope IN ('global',?) ORDER BY created_at", (scope,)
        ).fetchall()
    return [dict(row) for row in rows]


def remember(db_path: Path, scope: str, content: str, source_message_id: int | None = None) -> dict[str, Any]:
    if not isinstance(scope, str) or not scope or len(scope) > 120:
        raise ValueError("Memory scope must be a short project key or global")
    if not isinstance(content, str) or not content.strip() or len(content) > 500:
        raise ValueError("Memory must contain 1..500 characters")
    value = {"id": uuid.uuid4().hex, "scope": scope, "content": content.strip(),
             "source_message_id": source_message_id, "created_at": _now()}
    with _connect(db_path) as db:
        db.execute("INSERT INTO memories VALUES (?,?,?,?,?)", tuple(value.values()))
    return value


def forget(db_path: Path, identity: str) -> bool:
    with _connect(db_path) as db:
        count = db.execute("DELETE FROM memories WHERE id=?", (identity,)).rowcount
    return count == 1


def edit_memory(db_path: Path, identity: str, content: str) -> bool:
    if not isinstance(content, str) or not content.strip() or len(content) > 500:
        raise ValueError("Memory must contain 1..500 characters")
    with _connect(db_path) as db:
        count = db.execute("UPDATE memories SET content=? WHERE id=?",
                           (content.strip(), identity)).rowcount
    return count == 1


def _store_message(db_path: Path, session_id: str, role: str, content: str,
                   graph_hash: str, project_hash: str | None, detail: dict[str, Any]) -> None:
    with _connect(db_path) as db:
        if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
            raise ValueError("Unknown chat session")
        db.execute(
            "INSERT INTO messages(session_id,role,content,graph_sha256,project_sha256,detail_json,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, role, content, graph_hash, project_hash, canonical(detail), _now()),
        )


def ask(root: Path, db_path: Path, *, session_id: str, question: str,
        report: Path | None, model: str, ollama_url: str, use_model: bool) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("Question must contain 1..2000 characters")
    snapshot = active_snapshot(root)
    if snapshot is None:
        raise ValueError("Import a graph snapshot first")
    graph, manifest = snapshot
    graph_hash = manifest["graph_sha256"]
    selected = search_graph(graph, question)
    review_export = active_reviews(root)
    request = build_request(report, question) if report else None
    project_hash = request["report_sha256"] if request else None
    scope = project_hash or "global"
    notes = memories(db_path, scope)
    facts = request["facts"][:16] if request else []
    graph_items = [
        {"id": x["id"], "label": x["label"], "summary": str(x.get("summary", ""))[:600],
         "source": str(x.get("source", ""))[:200], "status": x["status"],
         "source_documents": x.get("sourceDocuments", [])}
        for x in selected["nodes"]
    ]
    graph_edges = [
        {"id": x["id"], "source": x["source"], "target": x["target"],
         "type": x.get("type"), "status": x["status"]}
        for x in selected["edges"]
    ]
    selected_ids = {x["id"] for x in selected["nodes"]}
    annotations = []
    if review_export and review_export["status"] == "user_annotation_only":
        for task in graph["verificationTasks"]:
            saved = review_export["reviews"].get(task["id"])
            if saved and selected_ids.intersection(task.get("entityIds", [])):
                annotations.append({"task_id": task["id"], "status": saved["status"],
                                    "evidence": saved["evidence"], "note": saved["note"]})
    evidence = {"project_status": request["project_status"] if request else "unassessed",
                "project_boundary": request["boundary"] if request else "No project report selected.",
                "project_facts": facts, "graph_nodes": graph_items, "graph_edges": graph_edges,
                "source_documents": [{"id": x["id"], "filename": x["filename"]}
                                     for x in graph["sourceDocuments"]],
                "review_annotations": annotations[:12],
                "review_status": review_export["status"] if review_export else "not_imported",
                "graph_status": "candidate_only", "graph_sha256": graph_hash,
                "project_sha256": project_hash}
    summary_lines = [
        f"所选项目验收状态：{evidence['project_status']}。这不证明 CFG 生成或 CAN 总线实测。"
        if request else "未选择工程报告；当前只显示图谱候选线索。",
    ]
    summary_lines += [f"{fact['pointer']} = {canonical(fact['value'])}"
                      for fact in facts if fact["pointer"].endswith(("/status", "/reason"))][:8]
    if graph_items:
        summary_lines.append("图谱候选节点：" + "、".join(f"{x['id']} {x['label']}" for x in graph_items))
    if graph_edges:
        summary_lines.append("图谱候选关系：" + "、".join(
            f"{x['id']} {x['source']}→{x['target']} ({x['type']})" for x in graph_edges))
    if annotations:
        summary_lines.append("相关核实工作单有用户注释；它们不改变图谱候选状态。")
    summary = "\n".join(summary_lines)
    _store_message(db_path, session_id, "user", question.strip(), graph_hash, project_hash, {})
    response: dict[str, Any] = {
        "status": "evidence_only", "summary": summary, "draft": "", "citations": [], "evidence": evidence,
        "model": None, "model_error": None, "semantic_status": "unassessed",
        "memory_count": len(notes),
    }
    if use_model and (facts or graph_items):
        client = OllamaModelClient(Endpoint(ollama_url, 60))
        context: dict[str, Any] | None = None
        try:
            identity = client.identity(model)
            version = client.service_version()
            model_evidence = {key: value for key, value in evidence.items()
                              if key not in {"review_annotations"}}
            context = {"question": question.strip(), "evidence": model_evidence,
                       "saved_preferences_and_decisions": [x["content"] for x in notes[:12]],
                       "boundary": "Graph entries are unverified candidates. Project facts are replayed evidence. "
                                   "Saved memory is a user preference, not evidence. "
                                   "Do not infer vendor generation, CAN runtime, or shared root causes."}
            completion = client.complete({
                "model": model, "stream": False, "think": False, "keep_alive": "2m",
                "messages": [
                    {"role": "system", "content": "用中文写不超过三句话的解释草稿。图谱节点和关系均为候选，必须称为待核实线索。工程状态只来自项目事实；长期记忆仅是用户偏好，不是证据。没有证据就说未知。不要编造总线运行或共同根因。"},
                    {"role": "user", "content": canonical(context)},
                ],
                "options": {"temperature": 0, "seed": 0, "num_ctx": 8192, "num_predict": 1400},
            })
            if (not isinstance(completion, dict) or completion.get("done") is not True
                    or completion.get("done_reason") != "stop" or completion.get("model") != model
                    or not isinstance(completion.get("message"), dict)
                    or completion["message"].get("role") != "assistant"
                    or not isinstance(completion["message"].get("content"), str)
                    or not completion["message"]["content"].strip()
                    or len(completion["message"]["content"]) > 4000):
                raise ValueError("incomplete_or_invalid_model_response")
            if client.identity(model) != identity:
                raise ValueError("Model identity changed during answer")
            response.update(status="draft_unassessed", draft=completion["message"]["content"],
                            model={"name": model,
                            "digest": identity["digest"], "service_version": version,
                            "input_tokens": completion.get("prompt_eval_count"),
                            "output_tokens": completion.get("eval_count"),
                            "raw_sha256": hashlib.sha256(canonical(completion).encode()).hexdigest()})
        except (ServiceError, ValueError, TypeError, KeyError) as exc:
            response.update(status="model_unavailable", model_error=str(exc))
        finally:
            trace_id = uuid.uuid4().hex
            response["trace_id"] = trace_id
            trace_dir = root / "runs"
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / f"{trace_id}.json").write_text(
                json.dumps({"graph_sha256": graph_hash, "project_sha256": project_hash,
                            "project_report": str(report) if report else None,
                            "question": question.strip(), "model": model,
                            "context": context, "transport": client.records,
                            "result": response}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    _store_message(db_path, session_id, "assistant", response["summary"],
                   graph_hash, project_hash, response)
    return response
