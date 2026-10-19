from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.agent_evaluation import (
    implementation_digest,
    load_agent_evaluation_manifest,
)
from automotive_workbench.explanation_services import Endpoint, retrieve_for_agent
from automotive_workbench.knowledge_policy import load_agent_knowledge_policy
from automotive_workbench.project_explanation import canonical
from scripts.trusted_knowledge_fixture_service import (
    load_corpus,
    trusted_knowledge_service,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples/knowledge/p30-vector-official-corpus.json"
POLICY = ROOT / "examples/knowledge/p30-vector-official-policy.json"
MANIFEST = ROOT / "docs/research/p30-agent-explanation-review-v1-manifest.json"


class TrustedKnowledgeFixtureTests(unittest.TestCase):
    def test_checked_in_cohort_is_pre_inference_frozen_to_current_code(self) -> None:
        manifest = load_agent_evaluation_manifest(MANIFEST)

        self.assertEqual(
            manifest["manifest_id"],
            "c99acf880ff7085ffb0f5821e8b0867415d91506df3a4aa8efb422ed13b95286",
        )
        self.assertEqual(manifest["implementation_sha256"], implementation_digest(ROOT))
        self.assertEqual(manifest["evaluation_id"], "p30-agent-explanation-review-v1")
        self.assertEqual(len(manifest["cases"]), 4)

    def test_official_corpus_and_policy_are_digest_bound(self) -> None:
        corpus = load_corpus(CORPUS)
        policy = load_agent_knowledge_policy(POLICY)

        self.assertEqual(
            {item["document_id"] for item in corpus["documents"]}, {101, 102}
        )
        self.assertEqual(
            {
                (item["document_id"], item["document_sha256"])
                for item in corpus["documents"]
            },
            {
                (item["document_id"], item["document_sha256"])
                for item in policy["documents"]
            },
        )
        self.assertTrue(
            all(
                item["source_url"].startswith("https://help.vector.com/")
                for item in corpus["documents"]
            )
        )

    def test_readonly_api_supplies_only_the_frozen_official_sources(self) -> None:
        policy = load_agent_knowledge_policy(POLICY)
        with trusted_knowledge_service(CORPUS) as (_, url):
            result = retrieve_for_agent(
                Endpoint(url, 5), "BSW identity mismatch and project validate", policy
            )

        self.assertEqual(
            {item["document_id"] for item in result["sources"]}, {101, 102}
        )
        self.assertTrue(
            all(item["authority"] == "official" for item in result["sources"])
        )
        self.assertTrue(
            all(
                "https://help.vector.com/" in item["excerpt"]
                for item in result["sources"]
            )
        )

    def test_content_tamper_is_rejected_before_service_start(self) -> None:
        corpus = load_corpus(CORPUS)
        changed = copy.deepcopy(corpus)
        changed["documents"][0]["chunks"][0]["content"] += " changed"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(canonical(changed) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "document digest"):
                load_corpus(path)


if __name__ == "__main__":
    unittest.main()
