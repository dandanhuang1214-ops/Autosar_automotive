"""Direct local Ollama chat, independent of Workbench evidence selection."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.explanation_services import Endpoint, ServiceError
from automotive_workbench.knowledge_chat import _connect, _store_message, history, memories
from automotive_workbench.model_client import OllamaModelClient
from automotive_workbench.project_explanation import canonical


def _context(db_path: Path, session_id: str) -> list[dict[str, str]]:
    """Replay only completed direct-chat turns from the selected session."""
    with _connect(db_path) as db:
        if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
            raise ValueError("Unknown chat session")
    turns: list[dict[str, str]] = []
    pending: str | None = None
    for message in history(db_path, session_id):
        detail = message["detail"]
        if detail.get("mode") != "general":
            pending = None
        elif message["role"] == "user":
            pending = message["content"]
        elif pending is not None and detail.get("status") == "answered":
            turns.extend(({"role": "user", "content": pending},
                          {"role": "assistant", "content": message["content"]}))
            pending = None
        else:
            pending = None
    recent = [{"role": item["role"],
               "content": item["content"][:4000] if item["role"] == "assistant" else item["content"]}
              for item in turns[-12:]]
    while len(recent) > 2 and sum(len(item["content"]) for item in recent) > 12_000:
        recent = recent[2:]
    return recent


def ask_general(root: Path, db_path: Path, *, session_id: str, question: str,
                model: str, ollama_url: str) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("Question must contain 1..2000 characters")
    previous = _context(db_path, session_id)
    saved = memories(db_path, "global")[-12:]
    prompt = [{"role": "system", "content": "你是本地 AI 助手。直接回答用户问题；不确定时说明不确定。不要声称已使用未提供的资料或工具。"},
              *([{"role": "system", "content": "用户明确保存的长期记忆（偏好和决定，不是事实来源）：\n"
                 + "\n".join(f"- {item['content']}" for item in saved)}] if saved else []),
              *previous, {"role": "user", "content": question.strip()}]
    client = OllamaModelClient(Endpoint(ollama_url, 120))
    called_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    response: dict[str, Any] = {
        "mode": "general", "status": "model_unavailable", "answer": "",
        "model_requested": True, "model_attempted": True,
        "model": None, "model_error": None, "called_at": called_at,
        "elapsed_ms": None, "timings_ms": {}, "memory_count": len(saved),
    }
    try:
        identity = client.identity(model)
        version = client.service_version()
        completion = client.complete({
            "model": model, "messages": prompt, "stream": False, "think": False,
            "keep_alive": "2m", "options": {"num_ctx": 8192, "num_predict": 2048},
        })
        if (not isinstance(completion, dict) or completion.get("done") is not True
                or completion.get("done_reason") != "stop" or completion.get("model") != model
                or not isinstance(completion.get("message"), dict)
                or completion["message"].get("role") != "assistant"
                or not isinstance(completion["message"].get("content"), str)
                or not completion["message"]["content"].strip()
                or len(completion["message"]["content"]) > 20_000):
            raise ValueError("incomplete_or_invalid_model_response")
        if client.identity(model) != identity:
            raise ValueError("Model identity changed during answer")
        timings = {key: round(completion[key] / 1_000_000, 1)
                   for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
                   if type(completion.get(key)) is int and completion[key] >= 0}
        response.update(
            status="answered", answer=completion["message"]["content"],
            model={"name": model, "digest": identity["digest"], "service_version": version,
                   "input_tokens": completion.get("prompt_eval_count"),
                   "output_tokens": completion.get("eval_count"),
                   "raw_sha256": hashlib.sha256(canonical(completion).encode()).hexdigest()},
            timings_ms=timings,
        )
    except (ServiceError, ValueError, TypeError, KeyError) as exc:
        response["model_error"] = str(exc)
    finally:
        response["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        trace_id = uuid.uuid4().hex
        response["trace_id"] = trace_id
        trace_dir = root / "runs"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{trace_id}.json").write_text(
            json.dumps({"mode": "general", "session_id": session_id,
                        "question": question.strip(), "model": model,
                        "called_at": called_at, "messages": prompt,
                        "transport": client.records, "result": response},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _store_message(db_path, session_id, "user", question.strip(), "none", None,
                   {"mode": "general"})
    _store_message(db_path, session_id, "assistant",
                   response["answer"] if response["answer"] else "Ollama 未返回可用回答。",
                   "none", None, response)
    return response
