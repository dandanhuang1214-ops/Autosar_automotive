"""Run a frozen, private graph chat cohort against local Ollama models."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from automotive_workbench.ai_chat import ask_general_stream
from automotive_workbench.chat_citation_audit import audit_trace
from automotive_workbench.knowledge_chat import new_session
from automotive_workbench.knowledge_graph_workspace import active_snapshot, import_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Cohort output already exists; choose a new directory")
    cohort_raw = args.cohort.read_bytes()
    cohort = json.loads(cohort_raw)
    active = active_snapshot(args.graph_root)
    if active is None or active[1]["graph_sha256"] != cohort["graph_sha256"]:
        raise ValueError("Frozen cohort graph does not match the active snapshot")
    digest = cohort["graph_sha256"]
    folder = args.graph_root / "snapshots" / digest
    sources = {name: (folder / name).read_bytes() for name in active[1]["source_files"]}
    imported = import_graph(args.output, (folder / "graph.json").read_bytes(), sources,
                            site_version="cohort-local-copy")
    if imported["graph_sha256"] != digest:
        raise ValueError("Private cohort graph copy changed")
    db = args.output / "chat.sqlite3"
    summary = []
    for model in args.model:
        for item in cohort["questions"]:
            session_id = new_session(db)
            started = time.perf_counter()
            first_delta_at: float | None = None

            def emit(kind, _payload):
                nonlocal first_delta_at
                if kind == "delta" and first_delta_at is None:
                    first_delta_at = time.perf_counter()

            response = ask_general_stream(
                args.output, db, session_id=session_id, question=item["question"],
                model=model, ollama_url=args.ollama_url,
                emit=emit, cancelled=lambda: False,
                register_client=lambda _client: None)
            evaluation_ms = response["timings_ms"].get("eval_duration")
            output_tokens = (response["model"] or {}).get("output_tokens")
            record = {"case_id": item["id"], "model": model,
                      "status": response["status"], "trace_id": response["trace_id"],
                      "knowledge_status": response["knowledge"]["status"],
                      "model_identity": response["model"],
                      "first_delta_ms": round((first_delta_at - started) * 1000, 1)
                      if first_delta_at is not None else None,
                      "elapsed_ms": response["elapsed_ms"],
                      "output_tokens": output_tokens,
                      "eval_tokens_per_second": round(output_tokens * 1000 / evaluation_ms, 1)
                      if isinstance(output_tokens, int) and evaluation_ms else None}
            if response["status"] == "answered":
                packet = audit_trace(args.output / "runs" / (response["trace_id"] + ".json"))
                record["target_retrieved"] = any(
                    source["source_id"] == item["target_chunk_id"]
                    for source in packet["sources"])
                record["citation_index_status"] = packet["citation_index_status"]
                (args.output / "reviews").mkdir(exist_ok=True)
                (args.output / "reviews" / (model.replace(":", "-") + "-" + item["id"] + ".json")).write_text(
                    json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary.append(record)
            print(f"{model} {item['id']}: {record['status']} / {record['knowledge_status']}", flush=True)
    (args.output / "summary.json").write_text(json.dumps({
        "format": "graph-chat-quality-run-0.1", "graph_sha256": digest,
        "cohort": str(args.cohort),
        "cohort_sha256": hashlib.sha256(cohort_raw).hexdigest(), "results": summary,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
