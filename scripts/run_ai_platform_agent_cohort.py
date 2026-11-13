"""Run the frozen AI platform cohort through a local chat or Agent web server."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from automotive_workbench.mcp_evidence_client import validate_endpoint

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / "docs/research/ai-platform-agent-cohort-20261112.json"


def _preflight_sources(cohort: dict) -> None:
    graph_hash = cohort["graph_sha256"]
    graph_path = ROOT / "output" / "knowledge-chat" / "snapshots" / graph_hash / "graph.json"
    graph_raw = graph_path.read_bytes()
    if hashlib.sha256(graph_raw).hexdigest() != graph_hash:
        raise ValueError("Frozen graph hash differs from the local snapshot")
    graph = json.loads(graph_raw)
    chunk_ids = {item["id"] for item in graph["chunks"]}
    output_root = (ROOT / "output").resolve()
    for case in cohort["cases"]:
        target = case.get("target_chunk_id")
        if target is not None and target not in chunk_ids:
            raise ValueError(f"Frozen target chunk does not exist: {case['id']}: {target}")
        if case.get("report"):
            report = (output_root / case["report"]).resolve()
            if (not report.is_relative_to(output_root)
                    or hashlib.sha256(report.read_bytes()).hexdigest() != cohort["project_report_sha256"]):
                raise ValueError(f"Frozen project report differs: {case['id']}")


def _get(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        return response.read(2_000_000)


def _post(url: str, token: str, value: dict) -> dict:
    request = Request(url, data=json.dumps(value, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "X-Workbench-Token": token})
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("Server returned a non-object result")
    return result


def _stream_chat(url: str, token: str, value: dict) -> tuple[dict, float | None]:
    request = Request(url, data=json.dumps(value, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "X-Workbench-Token": token})
    first_byte_ms = None
    result = None
    started = time.perf_counter()
    with urlopen(request, timeout=180) as response:
        for line in response:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "delta" and first_byte_ms is None:
                first_byte_ms = round((time.perf_counter() - started) * 1000, 1)
            if event.get("type") == "done":
                result = event
    if result is None:
        raise ValueError("Chat stream ended without completion")
    return result, first_byte_ms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--mode", choices=("agent", "chat", "stream-chat"), required=True)
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reuse the local URL boundary; the MCP path is only a sentinel for its origin.
    origin = args.server_url.rstrip("/")
    validate_endpoint(origin + "/mcp")
    cohort_raw = args.cohort.read_bytes()
    cohort = json.loads(cohort_raw)
    case_ids = {item["id"] for item in cohort["cases"]}
    if args.case and args.case not in case_ids:
        parser.error(f"Unknown case {args.case!r}; available: {', '.join(sorted(case_ids))}")
    _preflight_sources(cohort)
    html = _get(origin + "/").decode("utf-8")
    token_match = re.search(r"const token = '([^']+)';", html)
    if token_match is None:
        raise ValueError("Local chat token is missing")
    token = token_match.group(1)
    state = json.loads(_get(origin + "/api/state"))
    if state.get("active", {}).get("graph_sha256") != cohort["graph_sha256"]:
        raise ValueError("Active graph differs from frozen cohort")
    results = []
    for case in cohort["cases"]:
        if args.case and case["id"] != args.case:
            continue
        report = (ROOT / "output" / case["report"]).resolve() if case["report"] else None
        session = _post(origin + "/api/session", token, {})["session_id"]
        started = time.perf_counter()
        payload = ({"session_id": session, "goal": case["goal"],
                    "report": str(report) if report else ""} if args.mode == "agent"
                   else {"session_id": session, "question": case["goal"], "mode": "general"})
        if args.mode == "stream-chat":
            payload["request_id"] = str(uuid.uuid4())
            result, first_byte_ms = _stream_chat(origin + "/api/chat/stream", token, payload)
        else:
            result = _post(origin + ("/api/agent/run" if args.mode == "agent" else "/api/chat"),
                           token, payload)
            first_byte_ms = None
        results.append({"case_id": case["id"], "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                        "first_byte_ms": first_byte_ms, "result": result})
    record = {"format": "ai-platform-agent-cohort-run-0.1", "mode": args.mode,
              "server_url": origin, "provider": state.get("provider"), "model": state.get("model"),
              "cohort_sha256": hashlib.sha256(cohort_raw).hexdigest(),
              "ran_at": datetime.now(timezone.utc).isoformat(), "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "mode": args.mode,
                      "provider": record["provider"], "cases": [
                          {"id": item["case_id"], "status": item["result"].get("status"),
                           "elapsed_ms": item["elapsed_ms"],
                           "first_byte_ms": item["first_byte_ms"]} for item in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
