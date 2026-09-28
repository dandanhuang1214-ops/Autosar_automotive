"""Lexical navigation of the frozen question catalog; never an engineering answer."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from automotive_workbench.engineering_review import canonical, catalog, digest


def tokens(text: str) -> set[str]:
    result = set(re.findall(r"[a-z0-9]+", text.casefold()))
    for word in re.findall(r"[\u3400-\u9fff]+", text):
        result.update(word[i:i + 2] for i in range(len(word) - 1))
    return result


def search_questions(
    query: str, limit: int = 5, input_version: str | None = None,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ValueError("Search query must contain 1..512 characters")
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("Search limit must be an integer in 1..10")
    questions = catalog()["questions"]
    if input_version is not None and input_version not in {q["input_version"] for q in questions}:
        raise ValueError("Unsupported catalog input version")
    documents = [tokens(q["id"] + " " + q["question"]) for q in questions]
    frequency = Counter(t for document in documents for t in document)
    query_tokens = tokens(query)
    hits = []
    for question, document in zip(questions, documents):
        if input_version is not None and question["input_version"] != input_version:
            continue
        overlap = sorted(query_tokens & document)
        if not overlap:
            continue
        # Normalized IDF overlap. Fixed corpus, stable tie-break, no trained model.
        score = sum(math.log((len(documents) + 1) / (frequency[t] + 1)) + 1 for t in overlap) / math.sqrt(len(document))
        hits.append({
            "question_id": question["id"], "question": question["question"],
            "input_version": question["input_version"], "score": round(score, 8),
            "matched_tokens": overlap,
            "policy": "scope-refusal" if question["refusal"] else "recorded-facts",
        })
    hits.sort(key=lambda hit: (-hit["score"], hit["question_id"]))
    return {
        "schema_version": "engineering-question-search-0.1",
        "status": "matches" if hits else "no-match",
        "query": query, "limit": limit, "input_version": input_version,
        "catalog_sha256": digest(canonical(catalog()).encode()),
        "method": "idf-overlap-ascii-words-and-cjk-bigrams-0.1",
        "candidates": hits[:limit],
        "boundary": "Catalog navigation only. A match is not evidence or an answer; select a question and verify its source separately.",
    }
