from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.chat_citation_audit import audit_trace


class CitationAuditTest(unittest.TestCase):
    def test_invalid_index_is_separate_from_semantic_review(self) -> None:
        trace = {
            "mode": "general", "question": "CanIf 做什么？",
            "messages": [{"role": "system", "content": "[资料1] CanIf\n只负责映射。"}],
            "result": {"status": "answered", "answer": "只负责映射。[资料1] 它还负责诊断服务。[资料3]",
                       "model": {"name": "fixture", "digest": "a" * 64},
                       "knowledge": {"status": "graph_candidates", "graph_sha256": "b" * 64,
                                     "sources": [{"source_id": "T1", "document_id": "D1",
                                                  "document_sha256": "c" * 64,
                                                  "excerpt": "只负责映射。"}]}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
            packet = audit_trace(path)
            self.assertEqual(packet["citation_index_status"], "invalid")
            self.assertEqual(packet["invalid_indices"], [3])
            self.assertEqual(packet["semantic_status"], "pending_human_review")
            self.assertEqual(packet["sentence_reviews"][0]["cited_indices"], [1])
            self.assertTrue(all(item["support"] == "pending_human_review"
                                for item in packet["sentence_reviews"]))
            trace["messages"][0]["content"] = "[资料1] CanIf\n不同的内容。"
            path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent from the model prompt"):
                audit_trace(path)


if __name__ == "__main__":
    unittest.main()
