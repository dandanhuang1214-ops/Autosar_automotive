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
COHORT = ROOT / "docs/research/ai-platform-agent-cohort-20261112.json"


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
    parser.add_argument("--case", choices=("graph-only", "project-only", "combined"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reuse the local URL boundary; the MCP path is only a sentinel for its origin.
    origin = args.server_url.rstrip("/")
    validate_endpoint(origin + "/mcp")
    cohort_raw = COHORT.read_bytes()
    cohort = json.loads(cohort_raw)
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
        if report and hashlib.sha256(report.read_bytes()).hexdigest() != cohort["project_report_sha256"]:
            raise ValueError("Project report differs from frozen cohort")
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
