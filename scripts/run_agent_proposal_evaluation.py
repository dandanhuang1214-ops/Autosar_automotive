"""Run a frozen read-then-propose cohort against the pinned Ollama model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from automotive_workbench.agent_proposal_evaluation import (
    run_agent_proposal_evaluation,
)
from automotive_workbench.explanation_services import Endpoint
from automotive_workbench.model_client import OllamaModelClient


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
    result = run_agent_proposal_evaluation(
        args.root,
        args.implementation_root,
        args.manifest,
        args.manifest_id,
        args.output,
        client=OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
