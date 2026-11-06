"""Prepare an exact-source review packet for a saved graph-backed chat turn.

Index checks are mechanical. A reviewer must judge whether each answer claim is
actually supported by its cited candidate excerpt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_CITATION = re.compile(r"\[\s*资料\s*([0-9]+)\s*\]")
_SENTENCE = re.compile(r".*?(?:[。！？!?；;]\s*(?:\[\s*资料\s*[0-9]+\s*\])?|\n|$)", re.DOTALL)


def audit_trace(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    trace = json.loads(raw)
    result = trace.get("result", {})
    knowledge = result.get("knowledge", {})
    sources = knowledge.get("sources", [])
    answer = result.get("answer", "")
    if (trace.get("mode") != "general" or result.get("status") != "answered"
            or knowledge.get("status") != "graph_candidates"
            or not isinstance(answer, str) or not answer.strip()
            or not isinstance(sources, list) or not sources):
        raise ValueError("Expected a completed graph-backed general chat trace")
    prompts = [item.get("content", "") for item in trace.get("messages", [])
               if isinstance(item, dict) and item.get("role") == "system"]
    source_prompt = "\n".join(prompts)
    indexed_sources = []
    for index, source in enumerate(sources, 1):
        excerpt = source.get("excerpt")
        if (not isinstance(excerpt, str) or not excerpt.strip()
                or f"[资料{index}]" not in source_prompt or excerpt not in source_prompt):
            raise ValueError("Trace source is absent from the model prompt")
        indexed_sources.append({"index": index, "source_id": source["source_id"],
                                "document_id": source["document_id"],
                                "document_sha256": source["document_sha256"],
                                "excerpt": excerpt})
    cited = sorted({int(value) for value in _CITATION.findall(answer)})
    invalid = [index for index in cited if index < 1 or index > len(sources)]
    sentences = [item.strip() for item in _SENTENCE.findall(answer) if item.strip()]
    return {
        "format": "graph-chat-citation-review-0.1",
        "trace_sha256": hashlib.sha256(raw).hexdigest(),
        "graph_sha256": knowledge["graph_sha256"],
        "model": result.get("model"),
        "question": trace.get("question"),
        "answer": answer,
        "sources": indexed_sources,
        "citation_index_status": "invalid" if invalid else "indexed" if cited else "missing",
        "cited_indices": cited,
        "invalid_indices": invalid,
        "semantic_status": "pending_human_review",
        "sentence_reviews": [{"text": sentence,
                              "cited_indices": [int(value) for value in _CITATION.findall(sentence)],
                              "support": "pending_human_review"}
                             for sentence in sentences],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    packet = audit_trace(args.trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
