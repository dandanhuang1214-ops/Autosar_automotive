"""Run a frozen evidence-plan reference comparison against Ollama."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from automotive_workbench.agent_evidence_comparison import (
    load_agent_evidence_comparison_manifest,
    run_agent_evidence_comparison,
)
from automotive_workbench.explanation_services import Endpoint
from automotive_workbench.model_client import OllamaModelClient
from trusted_knowledge_fixture_service import trusted_knowledge_service


def run(
    root: Path,
    implementation_root: Path,
    manifest: Path,
    manifest_id: str,
    output: Path,
    ollama_url: str,
    timeout: float,
) -> dict:
    frozen = load_agent_evidence_comparison_manifest(manifest)
    corpus = root / frozen["knowledge_corpus"]["path"]
    with trusted_knowledge_service(corpus) as (_, knowledge_url):
        return run_agent_evidence_comparison(
            root,
            implementation_root,
            manifest,
            manifest_id,
            output,
            client=OllamaModelClient(Endpoint(ollama_url, timeout)),
            knowledge_endpoint=Endpoint(knowledge_url, timeout),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--implementation-root", type=Path, required=True)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.root,
                args.implementation_root,
                args.manifest,
                args.manifest_id,
                args.output,
                args.ollama_url,
                args.timeout,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
