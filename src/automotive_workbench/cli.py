from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

from automotive_workbench.ecuc_project import run_inspection, verify_inspection
from automotive_workbench.davinci_mapping import audit_mappings
from automotive_workbench.ecuc_communication import run_communication, verify_communication
from automotive_workbench.ecuc_review import run_review as run_ecuc_review, verify_review as verify_ecuc_review
from automotive_workbench.ecuc_impact import compare_reviews as compare_ecuc_reviews, verify_impact as verify_ecuc_impact
from automotive_workbench.adapters.generate_arxml import summarize_issue_report
from automotive_workbench.adapters.dbc import inspect_dbc, validate_dbc_intent
from automotive_workbench.adapters.canonical_contract import validate_contract_mapping
from automotive_workbench.bsw_intent import trace_signal
from automotive_workbench.communication_graph import run_graph, verify_graph_report
from automotive_workbench.external_ecu import run_external_ecu, verify_external_ecu
from automotive_workbench.experiment import run_suite
from automotive_workbench.can_runtime import run_can_lab
from automotive_workbench.can_supervision import run_can_supervision
from automotive_workbench.can_io import BusConfig, capture_log, decode_log, open_bus, replay_log, run_log_lab
from automotive_workbench.can_backend import probe_can_backend, run_backend_lab
from automotive_workbench.adapters.openbsw_patch import prepare_openbsw_patch
from automotive_workbench.diag_intent import summarize_uds_intent
from automotive_workbench.dtc_intent import summarize_dtc_intent
from automotive_workbench.dtc_lifecycle import run_dtc_lifecycle
from automotive_workbench.dtc_aging import run_dtc_aging_lab
from automotive_workbench.dtc_reset import run_dtc_reset_lab
from automotive_workbench.dtc_persistence_fault import run_dtc_persistence_fault_lab
from automotive_workbench.dtc_redundancy import run_dtc_redundancy_lab
from automotive_workbench.dtc_redundancy_repair import run_dtc_redundancy_repair_lab
from automotive_workbench.review import run_review
from automotive_workbench.review_eval import run_review_evaluation
from automotive_workbench.uds_runtime import probe_uds_backend, run_uds_lab
from automotive_workbench.uds_client import read_uds_did
from automotive_workbench.communication_evidence import run_communication_chain
from automotive_workbench.communication_delivery import run_communication_delivery
from automotive_workbench.communication_runtime import default_communication_config
from automotive_workbench.communication_plan import preflight_communication
from automotive_workbench.declared_communication import run_declared_communication
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    verify_evidence_bundle,
)
from automotive_workbench.evidence_capsule import export_evidence_capsule
from automotive_workbench.evidence_capsule_verification import verify_evidence_capsule
from automotive_workbench.project_workflow import run_project
from automotive_workbench.arxml_bridge import run_arxml, verify_report
from automotive_workbench.project_review import run_project_review
from automotive_workbench.engineering_review import (
    catalog, run_engineering_review, verify_engineering_review,
)
from automotive_workbench.engineering_search import search_questions
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)


def _print_json(result: dict) -> None:
    """Keep redirected JSON valid on consoles that cannot encode source text."""
    text = json.dumps(result, ensure_ascii=False, indent=2)
    try:
        text.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
    except UnicodeEncodeError:
        text = json.dumps(result, ensure_ascii=True, indent=2)
    print(text)


def _utc_now_at_or_after(recorded: str) -> datetime:
    """Keep CLI-authored ledger time monotonic across host clock corrections."""
    now = datetime.now(timezone.utc)
    previous = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
    if previous.tzinfo is None:
        raise ValueError("Recorded transaction time requires a timezone")
    return max(now, previous.astimezone(timezone.utc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workbench")
    commands = parser.add_subparsers(dest="command", required=True)

    mapping = commands.add_parser("audit-signal-mappings", help="Audit explicit ARXML data-element to system-signal mappings")
    mapping.add_argument("--source", type=Path, action="append", required=True)
    mapping.add_argument("--output", type=Path, required=True)

    ecuc = commands.add_parser("inspect-ecuc-project", help="Inspect selected DPA/ECUC structure without invoking vendor tools")
    ecuc.add_argument("project", type=Path)
    ecuc.add_argument("--output", type=Path, required=True)
    ecuc_verify = commands.add_parser("verify-ecuc-inspection", help="Replay a portable ECUC inspection snapshot")
    ecuc_verify.add_argument("report", type=Path)
    ecuc_chain = commands.add_parser("trace-ecuc-communication", help="Trace explicit Com/PduR/CanIf/Can ECUC references")
    ecuc_chain.add_argument("project", type=Path)
    ecuc_chain.add_argument("--output", type=Path, required=True)
    ecuc_chain_verify = commands.add_parser("verify-ecuc-communication", help="Replay ECUC communication chains from portable sources")
    ecuc_chain_verify.add_argument("report", type=Path)
    ecuc_review = commands.add_parser("review-ecuc-project", help="Review ECUC communication, application/task binding, modes and historical logs")
    ecuc_review.add_argument("project", type=Path)
    ecuc_review.add_argument("--application", type=Path, action="append", default=[])
    ecuc_review.add_argument("--tool-log", type=Path, action="append", default=[])
    ecuc_review.add_argument("--output", type=Path, required=True)
    ecuc_review_verify = commands.add_parser("verify-ecuc-review", help="Replay a portable ECUC engineering review")
    ecuc_review_verify.add_argument("report", type=Path)
    ecuc_compare = commands.add_parser("compare-ecuc-reviews", help="Compare verified ECUC snapshots and trace structural impact")
    ecuc_compare.add_argument("before", type=Path)
    ecuc_compare.add_argument("after", type=Path)
    ecuc_compare.add_argument("--output", type=Path, required=True)
    ecuc_impact_verify = commands.add_parser("verify-ecuc-impact", help="Replay a portable ECUC configuration impact bundle")
    ecuc_impact_verify.add_argument("report", type=Path)

    commands.add_parser("list-engineering-questions", help="List bounded, versioned P21-P23 evidence questions")
    search = commands.add_parser("search-engineering-questions", help="Find catalog questions; matches are not engineering conclusions")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--input-version")
    engineering = commands.add_parser("review-engineering", help="Answer a fixed engineering question with replay-verified structured citations")
    engineering.add_argument("report", type=Path)
    engineering.add_argument("--question", required=True)
    engineering.add_argument("--output", type=Path, required=True)
    engineering_verify = commands.add_parser("verify-engineering-review", help="Recompute an engineering answer and all source citations offline")
    engineering_verify.add_argument("report", type=Path)

    for command in ("import-arxml", "compare-arxml"):
        arxml_parser = commands.add_parser(command, help="Import/compare the audited SWC ARXML subset")
        arxml_parser.add_argument("source", type=Path)
        if command == "compare-arxml":
            arxml_parser.add_argument("candidate", type=Path)
        arxml_parser.add_argument("--provenance", type=Path)
        arxml_parser.add_argument("--output", type=Path, required=True)
    arxml_verify = commands.add_parser("verify-arxml", help="Replay embedded XML and verify import/comparison conclusions")
    arxml_verify.add_argument("report", type=Path)

    graph_verify = commands.add_parser("verify-communication-graph", help="Replay embedded graph/impact sources and check saved conclusions")
    graph_verify.add_argument("report", type=Path)
    graph_parser = commands.add_parser("build-communication-graph", help="Build a source-bound communication configuration graph")
    graph_parser.add_argument("project", type=Path)
    graph_parser.add_argument("--output", type=Path, required=True)
    impact_parser = commands.add_parser("compare-communication-config", help="Trace configuration changes to affected objects and acceptance IDs")
    impact_parser.add_argument("project", type=Path)
    impact_parser.add_argument("candidate", type=Path)
    impact_parser.add_argument("--output", type=Path, required=True)

    plan_parser = commands.add_parser("plan-communication", help="Preflight declared CAN vectors without opening a bus or writing files")
    plan_parser.add_argument("dbc", type=Path)
    plan_parser.add_argument("intent", type=Path)
    plan_parser.add_argument("declaration", type=Path)

    declared_parser = commands.add_parser("run-declared-communication", help="Execute preflighted classic CAN vectors with a local peer")
    declared_parser.add_argument("dbc", type=Path)
    declared_parser.add_argument("intent", type=Path)
    declared_parser.add_argument("declaration", type=Path)
    declared_parser.add_argument("--output", type=Path, required=True)
    declared_parser.add_argument("--interface", choices=["virtual", "socketcan"], default="virtual")
    declared_parser.add_argument("--channel")

    ecuc_project_verify = commands.add_parser("verify-ecuc-project", help="Replay a static ECUC project-acceptance-0.6/0.7/0.8 bundle")
    ecuc_project_verify.add_argument("report", type=Path)

    project_parser = commands.add_parser("run-project", help="Validate and run a project with requirement acceptance evidence")
    project_parser.add_argument("project", type=Path)
    project_parser.add_argument("--output", type=Path, required=True)
    project_parser.add_argument("--interface", choices=["virtual", "socketcan"], default="virtual")
    project_parser.add_argument("--channel")

    model_explanation = commands.add_parser("explain-project", help="Explain verified evidence with local Ollama and optional existing knowledge search")
    model_explanation.add_argument("report", type=Path)
    model_explanation.add_argument("--question", required=True)
    model_explanation.add_argument("--output", type=Path, required=True)
    model_explanation.add_argument("--model", required=True)
    model_explanation.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    model_explanation.add_argument("--knowledge-url")
    model_explanation.add_argument("--knowledge-query")
    model_explanation.add_argument("--timeout", type=float, default=30)
    model_verify = commands.add_parser("verify-model-explanation", help="Replay a saved model explanation without network access")
    model_verify.add_argument("report", type=Path)
    model_verify.add_argument("directory", type=Path)
    agent_knowledge = commands.add_parser(
        "retrieve-agent-knowledge",
        help="Read knowledge through an explicit digest-bound Agent allowlist",
    )
    agent_knowledge.add_argument("policy", type=Path)
    agent_knowledge.add_argument("--query", required=True)
    agent_knowledge.add_argument("--knowledge-url", required=True)
    agent_knowledge.add_argument("--timeout", type=float, default=30)
    readonly_agent = commands.add_parser(
        "run-readonly-agent",
        help="Run a budgeted Agent over bound read-only project and knowledge tools",
    )
    readonly_agent.add_argument("report", type=Path)
    readonly_agent.add_argument("--goal", required=True)
    readonly_agent.add_argument("--model", required=True)
    readonly_agent.add_argument("--output", type=Path, required=True)
    readonly_agent.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    readonly_agent.add_argument("--knowledge-url")
    readonly_agent.add_argument("--knowledge-policy", type=Path)
    readonly_agent.add_argument("--timeout", type=float, default=30)
    readonly_agent.add_argument("--max-steps", type=int, default=4)
    readonly_agent.add_argument("--max-model-calls", type=int, default=4)
    readonly_agent.add_argument("--max-tool-calls", type=int, default=3)
    readonly_agent.add_argument("--max-total-tokens", type=int, default=4096)
    readonly_agent.add_argument("--max-output-tokens-per-call", type=int, default=256)
    readonly_agent.add_argument("--context-window", type=int, default=8192)
    readonly_agent.add_argument("--max-seconds", type=float, default=120)
    readonly_agent.add_argument("--max-observation-chars", type=int, default=20_000)
    readonly_agent.add_argument(
        "--pause-after-tool-calls",
        type=int,
        help="Pause at a safe boundary after this many successful read tools",
    )
    readonly_agent_verify = commands.add_parser(
        "verify-readonly-agent-trace",
        help="Verify a saved read-only Agent trace without model or knowledge services",
    )
    readonly_agent_verify.add_argument("trace", type=Path)
    evidence_plan_create = commands.add_parser(
        "create-agent-evidence-plan",
        help="Seal a deterministic read-tool sequence before model summarization",
    )
    evidence_plan_create.add_argument("--goal", required=True)
    evidence_plan_create.add_argument(
        "--scope",
        choices=[
            "project_detail",
            "reviewed_knowledge",
            "project_and_reviewed_knowledge",
        ],
        required=True,
    )
    evidence_plan_create.add_argument("--output", type=Path, required=True)
    evidence_plan_verify = commands.add_parser(
        "verify-agent-evidence-plan",
        help="Verify a deterministic Agent evidence plan offline",
    )
    evidence_plan_verify.add_argument("plan", type=Path)
    evidence_plan_run = commands.add_parser(
        "run-agent-evidence-plan",
        help="Run planned read tools and one evidence-bound structured summary",
    )
    evidence_plan_run.add_argument("report", type=Path)
    evidence_plan_run.add_argument("plan", type=Path)
    evidence_plan_run.add_argument("--model", required=True)
    evidence_plan_run.add_argument("--output", type=Path, required=True)
    evidence_plan_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    evidence_plan_run.add_argument("--knowledge-url")
    evidence_plan_run.add_argument("--knowledge-policy", type=Path)
    evidence_plan_run.add_argument("--timeout", type=float, default=30)
    evidence_plan_run.add_argument("--max-steps", type=int, default=3)
    evidence_plan_run.add_argument("--max-model-calls", type=int, default=1)
    evidence_plan_run.add_argument("--max-tool-calls", type=int, default=2)
    evidence_plan_run.add_argument("--max-total-tokens", type=int, default=4096)
    evidence_plan_run.add_argument(
        "--max-output-tokens-per-call", type=int, default=512
    )
    evidence_plan_run.add_argument("--context-window", type=int, default=8192)
    evidence_plan_run.add_argument("--max-seconds", type=float, default=120)
    evidence_plan_run.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    evidence_result_verify = commands.add_parser(
        "verify-agent-evidence-plan-result",
        help="Verify a plan-bound Agent explanation result without services",
    )
    evidence_result_verify.add_argument("plan", type=Path)
    evidence_result_verify.add_argument("result", type=Path)
    evidence_summary_run = commands.add_parser(
        "run-agent-evidence-summary",
        help="Run a fixed evidence plan and one bounded plain-text summary",
    )
    evidence_summary_run.add_argument("report", type=Path)
    evidence_summary_run.add_argument("plan", type=Path)
    evidence_summary_run.add_argument("--model", required=True)
    evidence_summary_run.add_argument("--output", type=Path, required=True)
    evidence_summary_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    evidence_summary_run.add_argument("--knowledge-url")
    evidence_summary_run.add_argument("--knowledge-policy", type=Path)
    evidence_summary_run.add_argument("--timeout", type=float, default=30)
    evidence_summary_run.add_argument("--max-steps", type=int, default=3)
    evidence_summary_run.add_argument("--max-model-calls", type=int, default=1)
    evidence_summary_run.add_argument("--max-tool-calls", type=int, default=2)
    evidence_summary_run.add_argument("--max-total-tokens", type=int, default=4096)
    evidence_summary_run.add_argument(
        "--max-output-tokens-per-call", type=int, default=512
    )
    evidence_summary_run.add_argument("--context-window", type=int, default=8192)
    evidence_summary_run.add_argument("--max-seconds", type=float, default=120)
    evidence_summary_run.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    evidence_summary_verify = commands.add_parser(
        "verify-agent-evidence-summary-result",
        help="Verify a plain-text evidence summary without model or knowledge services",
    )
    evidence_summary_verify.add_argument("plan", type=Path)
    evidence_summary_verify.add_argument("result", type=Path)
    evidence_pair_plan_create = commands.add_parser(
        "create-agent-evidence-pair-plan",
        help="Seal named checks that each require a complete status/reason pair",
    )
    evidence_pair_plan_create.add_argument("--goal", required=True)
    evidence_pair_plan_create.add_argument(
        "--check-id", action="append", required=True, dest="check_ids"
    )
    evidence_pair_plan_create.add_argument("--output", type=Path, required=True)
    evidence_pair_plan_verify = commands.add_parser(
        "verify-agent-evidence-pair-plan",
        help="Verify a complete evidence-pair plan offline",
    )
    evidence_pair_plan_verify.add_argument("plan", type=Path)
    evidence_pair_summary_run = commands.add_parser(
        "run-agent-evidence-pair-summary",
        help="Refuse incomplete pairs or run one bounded plain-text summary",
    )
    evidence_pair_summary_run.add_argument("report", type=Path)
    evidence_pair_summary_run.add_argument("plan", type=Path)
    evidence_pair_summary_run.add_argument("--model", required=True)
    evidence_pair_summary_run.add_argument("--output", type=Path, required=True)
    evidence_pair_summary_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    evidence_pair_summary_run.add_argument("--timeout", type=float, default=30)
    evidence_pair_summary_run.add_argument("--max-steps", type=int, default=2)
    evidence_pair_summary_run.add_argument("--max-model-calls", type=int, default=1)
    evidence_pair_summary_run.add_argument("--max-tool-calls", type=int, default=1)
    evidence_pair_summary_run.add_argument("--max-total-tokens", type=int, default=4096)
    evidence_pair_summary_run.add_argument(
        "--max-output-tokens-per-call", type=int, default=512
    )
    evidence_pair_summary_run.add_argument("--context-window", type=int, default=8192)
    evidence_pair_summary_run.add_argument("--max-seconds", type=float, default=120)
    evidence_pair_summary_run.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    evidence_pair_summary_v06_run = commands.add_parser(
        "run-agent-evidence-pair-summary-v06",
        help="Bind each selected pair to its exact report requirement text before model inference",
    )
    evidence_pair_summary_v06_run.add_argument("report", type=Path)
    evidence_pair_summary_v06_run.add_argument("plan", type=Path)
    evidence_pair_summary_v06_run.add_argument("--model", required=True)
    evidence_pair_summary_v06_run.add_argument("--output", type=Path, required=True)
    evidence_pair_summary_v06_run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    evidence_pair_summary_v06_run.add_argument("--timeout", type=float, default=30)
    evidence_pair_summary_v06_run.add_argument("--max-steps", type=int, default=2)
    evidence_pair_summary_v06_run.add_argument("--max-model-calls", type=int, default=1)
    evidence_pair_summary_v06_run.add_argument("--max-tool-calls", type=int, default=1)
    evidence_pair_summary_v06_run.add_argument("--max-total-tokens", type=int, default=4096)
    evidence_pair_summary_v06_run.add_argument("--max-output-tokens-per-call", type=int, default=512)
    evidence_pair_summary_v06_run.add_argument("--context-window", type=int, default=8192)
    evidence_pair_summary_v06_run.add_argument("--max-seconds", type=float, default=120)
    evidence_pair_summary_v06_run.add_argument("--max-observation-chars", type=int, default=20_000)
    evidence_pair_summary_v06_verify = commands.add_parser(
        "verify-agent-evidence-pair-summary-result-v06",
        help="Verify report-bound requirement text, model request, and trace offline",
    )
    evidence_pair_summary_v06_verify.add_argument("report", type=Path)
    evidence_pair_summary_v06_verify.add_argument("plan", type=Path)
    evidence_pair_summary_v06_verify.add_argument("result", type=Path)
    evidence_pair_summary_verify = commands.add_parser(
        "verify-agent-evidence-pair-summary-result",
        help="Verify a complete evidence-pair summary without model services",
    )
    evidence_pair_summary_verify.add_argument("report", type=Path)
    evidence_pair_summary_verify.add_argument("plan", type=Path)
    evidence_pair_summary_verify.add_argument("result", type=Path)
    evidence_pair_summary_v04_run = commands.add_parser(
        "run-agent-evidence-pair-summary-v04",
        help="Run pair summary v0.4 with a control-plane-appended evidence boundary",
    )
    evidence_pair_summary_v04_run.add_argument("report", type=Path)
    evidence_pair_summary_v04_run.add_argument("plan", type=Path)
    evidence_pair_summary_v04_run.add_argument("--model", required=True)
    evidence_pair_summary_v04_run.add_argument("--output", type=Path, required=True)
    evidence_pair_summary_v04_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    evidence_pair_summary_v04_run.add_argument("--timeout", type=float, default=30)
    evidence_pair_summary_v04_run.add_argument("--max-steps", type=int, default=2)
    evidence_pair_summary_v04_run.add_argument("--max-model-calls", type=int, default=1)
    evidence_pair_summary_v04_run.add_argument("--max-tool-calls", type=int, default=1)
    evidence_pair_summary_v04_run.add_argument("--max-total-tokens", type=int, default=4096)
    evidence_pair_summary_v04_run.add_argument(
        "--max-output-tokens-per-call", type=int, default=512
    )
    evidence_pair_summary_v04_run.add_argument("--context-window", type=int, default=8192)
    evidence_pair_summary_v04_run.add_argument("--max-seconds", type=float, default=120)
    evidence_pair_summary_v04_run.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    evidence_pair_summary_v04_verify = commands.add_parser(
        "verify-agent-evidence-pair-summary-result-v04",
        help="Verify a pair summary v0.4 and its deterministic evidence boundary",
    )
    evidence_pair_summary_v04_verify.add_argument("report", type=Path)
    evidence_pair_summary_v04_verify.add_argument("plan", type=Path)
    evidence_pair_summary_v04_verify.add_argument("result", type=Path)
    evidence_pair_presentation_v05 = commands.add_parser(
        "render-agent-evidence-pairs-v05",
        help="Render exact verified status/reason pairs; keep model prose separate",
    )
    evidence_pair_presentation_v05.add_argument("report", type=Path)
    evidence_pair_presentation_v05.add_argument("plan", type=Path)
    evidence_pair_presentation_v05.add_argument("source_result", type=Path)
    evidence_pair_presentation_v05.add_argument("--output", type=Path, required=True)
    evidence_pair_presentation_v05_verify = commands.add_parser(
        "verify-agent-evidence-pairs-v05",
        help="Verify a v0.5 presentation against the original report and v0.4 result",
    )
    evidence_pair_presentation_v05_verify.add_argument("report", type=Path)
    evidence_pair_presentation_v05_verify.add_argument("plan", type=Path)
    evidence_pair_presentation_v05_verify.add_argument("result", type=Path)
    evidence_pair_presentation_v06 = commands.add_parser(
        "render-agent-evidence-pairs-v06",
        help="Render verified pairs from a requirement-text v0.6 result",
    )
    evidence_pair_presentation_v06.add_argument("report", type=Path)
    evidence_pair_presentation_v06.add_argument("plan", type=Path)
    evidence_pair_presentation_v06.add_argument("source_result", type=Path)
    evidence_pair_presentation_v06.add_argument("--output", type=Path, required=True)
    evidence_pair_presentation_v06_verify = commands.add_parser(
        "verify-agent-evidence-pairs-v06",
        help="Verify deterministic v0.6 presentation offline",
    )
    evidence_pair_presentation_v06_verify.add_argument("report", type=Path)
    evidence_pair_presentation_v06_verify.add_argument("plan", type=Path)
    evidence_pair_presentation_v06_verify.add_argument("result", type=Path)
    evidence_pair_coverage_v07 = commands.add_parser(
        "assess-agent-evidence-pair-model-v07",
        help="Check literal pair coverage in separate v0.6 model prose",
    )
    evidence_pair_coverage_v07.add_argument("report", type=Path)
    evidence_pair_coverage_v07.add_argument("plan", type=Path)
    evidence_pair_coverage_v07.add_argument("presentation", type=Path)
    evidence_pair_coverage_v07.add_argument("--output", type=Path, required=True)
    evidence_pair_coverage_v07_verify = commands.add_parser(
        "verify-agent-evidence-pair-model-v07",
        help="Replay a literal model coverage result offline",
    )
    evidence_pair_coverage_v07_verify.add_argument("report", type=Path)
    evidence_pair_coverage_v07_verify.add_argument("plan", type=Path)
    evidence_pair_coverage_v07_verify.add_argument("presentation", type=Path)
    evidence_pair_coverage_v07_verify.add_argument("result", type=Path)
    evidence_comparison_freeze = commands.add_parser(
        "freeze-agent-evidence-comparison",
        help="Freeze pre-inference reference answers and evidence plans",
    )
    evidence_comparison_freeze.add_argument("spec", type=Path)
    evidence_comparison_freeze.add_argument("--root", type=Path, required=True)
    evidence_comparison_freeze.add_argument(
        "--implementation-root", type=Path, required=True
    )
    evidence_comparison_freeze.add_argument("--model", required=True)
    evidence_comparison_freeze.add_argument("--model-digest", required=True)
    evidence_comparison_freeze.add_argument("--knowledge-policy", required=True)
    evidence_comparison_freeze.add_argument("--knowledge-corpus", required=True)
    evidence_comparison_freeze.add_argument("--output", type=Path, required=True)
    evidence_comparison_freeze.add_argument("--max-steps", type=int, default=3)
    evidence_comparison_freeze.add_argument(
        "--max-model-calls", type=int, default=1
    )
    evidence_comparison_freeze.add_argument(
        "--max-tool-calls", type=int, default=2
    )
    evidence_comparison_freeze.add_argument(
        "--max-total-tokens", type=int, default=4096
    )
    evidence_comparison_freeze.add_argument(
        "--max-output-tokens-per-call", type=int, default=512
    )
    evidence_comparison_freeze.add_argument(
        "--context-window", type=int, default=8192
    )
    evidence_comparison_freeze.add_argument(
        "--max-seconds", type=float, default=120
    )
    evidence_comparison_freeze.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    evidence_comparison_manifest_verify = commands.add_parser(
        "verify-agent-evidence-comparison-manifest",
        help="Verify a frozen pre-inference evidence comparison manifest",
    )
    evidence_comparison_manifest_verify.add_argument("manifest", type=Path)
    evidence_comparison_verify = commands.add_parser(
        "verify-agent-evidence-comparison",
        help="Replay a completed evidence comparison without services",
    )
    evidence_comparison_verify.add_argument("manifest", type=Path)
    evidence_comparison_verify.add_argument("directory", type=Path)
    agent_checkpoint_verify = commands.add_parser(
        "verify-readonly-agent-checkpoint",
        help="Verify a paused read-only Agent checkpoint without services",
    )
    agent_checkpoint_verify.add_argument("checkpoint", type=Path)
    agent_resume = commands.add_parser(
        "resume-readonly-agent",
        help="Idempotently resume a verified read-only Agent checkpoint",
    )
    agent_resume.add_argument("report", type=Path)
    agent_resume.add_argument("checkpoint", type=Path)
    agent_resume.add_argument("--output", type=Path, required=True)
    agent_resume.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    agent_resume.add_argument("--knowledge-url")
    agent_resume.add_argument("--knowledge-policy", type=Path)
    agent_resume.add_argument("--timeout", type=float, default=30)
    agent_resume.add_argument("--pause-after-tool-calls", type=int)
    agent_resume_verify = commands.add_parser(
        "verify-readonly-agent-resume",
        help="Verify a checkpoint-bound resume result without services",
    )
    agent_resume_verify.add_argument("checkpoint", type=Path)
    agent_resume_verify.add_argument("result", type=Path)
    agent_candidate_issue = commands.add_parser(
        "issue-agent-action-candidate",
        help="Seal one exact control-plane action candidate without model inference",
    )
    agent_candidate_issue.add_argument("checkpoint", type=Path)
    agent_candidate_issue.add_argument("arguments", type=Path)
    agent_candidate_issue.add_argument("--tool-name", required=True)
    agent_candidate_issue.add_argument(
        "--evidence-id", action="append", required=True
    )
    agent_candidate_issue.add_argument("--output", type=Path, required=True)
    agent_candidate_verify = commands.add_parser(
        "verify-agent-action-candidate",
        help="Verify a checkpoint-bound control-plane action candidate offline",
    )
    agent_candidate_verify.add_argument("checkpoint", type=Path)
    agent_candidate_verify.add_argument("candidate", type=Path)
    agent_candidate_select = commands.add_parser(
        "select-agent-action-candidate",
        help="Ask the pinned model to select a sealed candidate ID or decline",
    )
    agent_candidate_select.add_argument("checkpoint", type=Path)
    agent_candidate_select.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_candidate_select.add_argument("--output", type=Path, required=True)
    agent_candidate_select.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    agent_candidate_select.add_argument("--timeout", type=float, default=30)
    agent_candidate_selection_verify = commands.add_parser(
        "verify-agent-candidate-selection",
        help="Verify a candidate-ID selection against its sealed candidates offline",
    )
    agent_candidate_selection_verify.add_argument("checkpoint", type=Path)
    agent_candidate_selection_verify.add_argument("selection", type=Path)
    agent_candidate_selection_verify.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_approval_from_candidate = commands.add_parser(
        "request-agent-approval-from-candidate",
        help="Create a pending approval for the exact selected candidate action",
    )
    agent_approval_from_candidate.add_argument("checkpoint", type=Path)
    agent_approval_from_candidate.add_argument("selection", type=Path)
    agent_approval_from_candidate.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_approval_from_candidate.add_argument("--reason", required=True)
    agent_approval_from_candidate.add_argument(
        "--expires-in-seconds", type=int, default=900
    )
    agent_approval_from_candidate.add_argument(
        "--output", type=Path, required=True
    )
    agent_approval_from_candidate_verify = commands.add_parser(
        "verify-agent-approval-from-candidate",
        help="Verify that an approval preserves the selected sealed candidate",
    )
    agent_approval_from_candidate_verify.add_argument("checkpoint", type=Path)
    agent_approval_from_candidate_verify.add_argument("selection", type=Path)
    agent_approval_from_candidate_verify.add_argument("request", type=Path)
    agent_approval_from_candidate_verify.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_intent_issue = commands.add_parser(
        "issue-agent-action-intent",
        help="Seal a typed control-plane action intent without model inference",
    )
    agent_intent_issue.add_argument("checkpoint", type=Path)
    agent_intent_issue.add_argument("spec", type=Path)
    agent_intent_issue.add_argument("--output", type=Path, required=True)
    agent_intent_verify = commands.add_parser(
        "verify-agent-action-intent",
        help="Verify a checkpoint-bound typed action intent offline",
    )
    agent_intent_verify.add_argument("checkpoint", type=Path)
    agent_intent_verify.add_argument("intent", type=Path)
    agent_admission = commands.add_parser(
        "admit-agent-action-candidates",
        help="Deterministically filter sealed candidates using a typed intent",
    )
    agent_admission.add_argument("checkpoint", type=Path)
    agent_admission.add_argument("intent", type=Path)
    agent_admission.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_admission.add_argument("--output", type=Path, required=True)
    agent_admission_verify = commands.add_parser(
        "verify-agent-action-admission",
        help="Recompute a typed candidate admission without model services",
    )
    agent_admission_verify.add_argument("checkpoint", type=Path)
    agent_admission_verify.add_argument("intent", type=Path)
    agent_admission_verify.add_argument("admission", type=Path)
    agent_admission_verify.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_approval_from_admission = commands.add_parser(
        "request-agent-approval-from-admission",
        help="Create a pending approval for one deterministically admitted action",
    )
    agent_approval_from_admission.add_argument("checkpoint", type=Path)
    agent_approval_from_admission.add_argument("intent", type=Path)
    agent_approval_from_admission.add_argument("admission", type=Path)
    agent_approval_from_admission.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_approval_from_admission.add_argument("--reason", required=True)
    agent_approval_from_admission.add_argument(
        "--expires-in-seconds", type=int, default=900
    )
    agent_approval_from_admission.add_argument("--output", type=Path, required=True)
    agent_approval_from_admission_verify = commands.add_parser(
        "verify-agent-approval-from-admission",
        help="Verify that approval preserves a deterministic action admission",
    )
    agent_approval_from_admission_verify.add_argument("checkpoint", type=Path)
    agent_approval_from_admission_verify.add_argument("intent", type=Path)
    agent_approval_from_admission_verify.add_argument("admission", type=Path)
    agent_approval_from_admission_verify.add_argument("request", type=Path)
    agent_approval_from_admission_verify.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    agent_action_proposal = commands.add_parser(
        "propose-agent-action",
        help="Ask the pinned model for one typed proposal without registering a handler",
    )
    agent_action_proposal.add_argument("checkpoint", type=Path)
    agent_action_proposal.add_argument("--output", type=Path, required=True)
    agent_action_proposal.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    agent_action_proposal.add_argument("--timeout", type=float, default=30)
    agent_action_proposal_verify = commands.add_parser(
        "verify-agent-action-proposal",
        help="Verify a checkpoint-bound action proposal without model services",
    )
    agent_action_proposal_verify.add_argument("checkpoint", type=Path)
    agent_action_proposal_verify.add_argument("proposal", type=Path)
    agent_approval_from_proposal = commands.add_parser(
        "request-agent-approval-from-proposal",
        help="Create a pending approval request for the exact proposed action",
    )
    agent_approval_from_proposal.add_argument("checkpoint", type=Path)
    agent_approval_from_proposal.add_argument("proposal", type=Path)
    agent_approval_from_proposal.add_argument("--reason", required=True)
    agent_approval_from_proposal.add_argument(
        "--expires-in-seconds", type=int, default=900
    )
    agent_approval_from_proposal.add_argument("--output", type=Path, required=True)
    agent_approval_request = commands.add_parser(
        "request-agent-approval",
        help="Record a non-executing approval request bound to a paused Agent",
    )
    agent_approval_request.add_argument("checkpoint", type=Path)
    agent_approval_request.add_argument("arguments", type=Path)
    agent_approval_request.add_argument("--tool-name", required=True)
    agent_approval_request.add_argument(
        "--permission", choices=["execute", "write", "hardware"], required=True
    )
    agent_approval_request.add_argument("--reason", required=True)
    agent_approval_request.add_argument(
        "--evidence-id", action="append", required=True
    )
    agent_approval_request.add_argument(
        "--expires-in-seconds", type=int, default=900
    )
    agent_approval_request.add_argument("--output", type=Path, required=True)
    agent_approval_decision = commands.add_parser(
        "decide-agent-approval",
        help="Record an approved or denied local operator decision",
    )
    agent_approval_decision.add_argument("checkpoint", type=Path)
    agent_approval_decision.add_argument("request", type=Path)
    agent_approval_decision.add_argument(
        "--decision", choices=["approved", "denied"], required=True
    )
    agent_approval_decision.add_argument("--actor", required=True)
    agent_approval_decision.add_argument("--reason", required=True)
    agent_approval_decision.add_argument("--output", type=Path, required=True)
    agent_approval_expiry = commands.add_parser(
        "expire-agent-approval",
        help="Record expiry after an approval request deadline",
    )
    agent_approval_expiry.add_argument("checkpoint", type=Path)
    agent_approval_expiry.add_argument("request", type=Path)
    agent_approval_expiry.add_argument("--output", type=Path, required=True)
    agent_approval_request_verify = commands.add_parser(
        "verify-agent-approval-request",
        help="Verify a checkpoint-bound approval request offline",
    )
    agent_approval_request_verify.add_argument("checkpoint", type=Path)
    agent_approval_request_verify.add_argument("request", type=Path)
    agent_approval_decision_verify = commands.add_parser(
        "verify-agent-approval-decision",
        help="Verify a terminal approval decision offline",
    )
    agent_approval_decision_verify.add_argument("checkpoint", type=Path)
    agent_approval_decision_verify.add_argument("request", type=Path)
    agent_approval_decision_verify.add_argument("decision", type=Path)
    agent_approval_claim = commands.add_parser(
        "claim-agent-approval",
        help="Claim one approved request in a local non-executing ledger",
    )
    agent_approval_claim.add_argument("checkpoint", type=Path)
    agent_approval_claim.add_argument("request", type=Path)
    agent_approval_claim.add_argument("decision", type=Path)
    agent_approval_claim.add_argument("--ledger", type=Path, required=True)
    agent_transaction_complete = commands.add_parser(
        "complete-agent-transaction",
        help="Record a simulated or aborted non-executing transaction receipt",
    )
    agent_transaction_complete.add_argument("checkpoint", type=Path)
    agent_transaction_complete.add_argument("request", type=Path)
    agent_transaction_complete.add_argument("decision", type=Path)
    agent_transaction_complete.add_argument("--ledger", type=Path, required=True)
    agent_transaction_complete.add_argument(
        "--outcome", choices=["simulated", "aborted"], required=True
    )
    agent_transaction_complete.add_argument("--reason", required=True)
    agent_transaction_verify = commands.add_parser(
        "verify-agent-transaction",
        help="Verify a local approval claim and optional terminal receipt",
    )
    agent_transaction_verify.add_argument("checkpoint", type=Path)
    agent_transaction_verify.add_argument("request", type=Path)
    agent_transaction_verify.add_argument("decision", type=Path)
    agent_transaction_verify.add_argument("--ledger", type=Path, required=True)
    agent_virtual_execute = commands.add_parser(
        "execute-agent-virtual-can",
        help="Explicitly run one claimed send on an isolated process-local virtual CAN bus",
    )
    agent_virtual_execute.add_argument("checkpoint", type=Path)
    agent_virtual_execute.add_argument("request", type=Path)
    agent_virtual_execute.add_argument("decision", type=Path)
    agent_virtual_execute.add_argument("--ledger", type=Path, required=True)
    agent_virtual_execute.add_argument(
        "--enable-virtual-execution",
        action="store_true",
        help="Required local execution gate; approval alone is not authorization",
    )
    agent_virtual_verify = commands.add_parser(
        "verify-agent-virtual-execution",
        help="Verify a claimed virtual execution attempt and receipt offline",
    )
    agent_virtual_verify.add_argument("checkpoint", type=Path)
    agent_virtual_verify.add_argument("request", type=Path)
    agent_virtual_verify.add_argument("decision", type=Path)
    agent_virtual_verify.add_argument("--ledger", type=Path, required=True)
    agent_eval_freeze = commands.add_parser(
        "freeze-readonly-agent-eval",
        help="Freeze held-out Agent questions and structural gold before inference",
    )
    agent_eval_freeze.add_argument("spec", type=Path)
    agent_eval_freeze.add_argument("--root", type=Path, required=True)
    agent_eval_freeze.add_argument("--implementation-root", type=Path)
    agent_eval_freeze.add_argument("--output", type=Path, required=True)
    agent_eval_freeze.add_argument("--model", required=True)
    agent_eval_freeze.add_argument("--model-digest", required=True)
    agent_eval_freeze.add_argument("--knowledge-policy")
    agent_eval_freeze.add_argument("--max-steps", type=int, default=4)
    agent_eval_freeze.add_argument("--max-model-calls", type=int, default=4)
    agent_eval_freeze.add_argument("--max-tool-calls", type=int, default=3)
    agent_eval_freeze.add_argument("--max-total-tokens", type=int, default=4096)
    agent_eval_freeze.add_argument(
        "--max-output-tokens-per-call", type=int, default=256
    )
    agent_eval_freeze.add_argument("--context-window", type=int, default=8192)
    agent_eval_freeze.add_argument("--max-seconds", type=float, default=120)
    agent_eval_freeze.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    agent_eval_run = commands.add_parser(
        "run-readonly-agent-eval",
        help="Run a frozen Agent cohort and score traces without an LLM judge",
    )
    agent_eval_run.add_argument("manifest", type=Path)
    agent_eval_run.add_argument("--root", type=Path, required=True)
    agent_eval_run.add_argument("--implementation-root", type=Path)
    agent_eval_run.add_argument("--manifest-id", required=True)
    agent_eval_run.add_argument("--output", type=Path, required=True)
    agent_eval_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    agent_eval_run.add_argument("--knowledge-url")
    agent_eval_run.add_argument("--timeout", type=float, default=30)
    agent_eval_verify = commands.add_parser(
        "verify-readonly-agent-eval",
        help="Re-score a saved Agent cohort from immutable traces without services",
    )
    agent_eval_verify.add_argument("manifest", type=Path)
    agent_eval_verify.add_argument("directory", type=Path)
    agent_review_prepare = commands.add_parser(
        "prepare-agent-human-review",
        help="Prepare a blind human-review pack from a verified Agent evaluation",
    )
    agent_review_prepare.add_argument("manifest", type=Path)
    agent_review_prepare.add_argument("evaluation_directory", type=Path)
    agent_review_prepare.add_argument("--implementation-root", type=Path, default=Path("."))
    agent_review_prepare.add_argument("--output", type=Path, required=True)
    agent_review_verify = commands.add_parser(
        "verify-agent-human-review",
        help="Reconstruct and verify an Agent human-review pack offline",
    )
    agent_review_verify.add_argument("manifest", type=Path)
    agent_review_verify.add_argument("evaluation_directory", type=Path)
    agent_review_verify.add_argument("directory", type=Path)
    agent_review_verify.add_argument("--implementation-root", type=Path, default=Path("."))
    agent_review_finalize = commands.add_parser(
        "finalize-agent-human-review",
        help="Finalize a completed human-review template as an immutable assessment",
    )
    agent_review_finalize.add_argument("pack", type=Path)
    agent_review_finalize.add_argument("draft", type=Path)
    agent_review_finalize.add_argument("--output", type=Path, required=True)
    agent_review_assessment_verify = commands.add_parser(
        "verify-agent-human-review-assessment",
        help="Verify a completed Agent human-review assessment offline",
    )
    agent_review_assessment_verify.add_argument("pack", type=Path)
    agent_review_assessment_verify.add_argument("assessment", type=Path)
    proposal_eval_freeze = commands.add_parser(
        "freeze-agent-proposal-eval",
        help="Freeze end-to-end action-proposal cases before target-model inference",
    )
    proposal_eval_freeze.add_argument("spec", type=Path)
    proposal_eval_freeze.add_argument("--root", type=Path, required=True)
    proposal_eval_freeze.add_argument("--implementation-root", type=Path)
    proposal_eval_freeze.add_argument("--output", type=Path, required=True)
    proposal_eval_freeze.add_argument("--model", required=True)
    proposal_eval_freeze.add_argument("--model-digest", required=True)
    proposal_eval_freeze.add_argument("--max-steps", type=int, default=3)
    proposal_eval_freeze.add_argument("--max-model-calls", type=int, default=3)
    proposal_eval_freeze.add_argument("--max-tool-calls", type=int, default=1)
    proposal_eval_freeze.add_argument("--max-total-tokens", type=int, default=4096)
    proposal_eval_freeze.add_argument(
        "--max-output-tokens-per-call", type=int, default=256
    )
    proposal_eval_freeze.add_argument("--context-window", type=int, default=8192)
    proposal_eval_freeze.add_argument("--max-seconds", type=float, default=120)
    proposal_eval_freeze.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    proposal_eval_run = commands.add_parser(
        "run-agent-proposal-eval",
        help="Run a frozen read-then-propose cohort without executing actions",
    )
    proposal_eval_run.add_argument("manifest", type=Path)
    proposal_eval_run.add_argument("--root", type=Path, required=True)
    proposal_eval_run.add_argument("--implementation-root", type=Path)
    proposal_eval_run.add_argument("--manifest-id", required=True)
    proposal_eval_run.add_argument("--output", type=Path, required=True)
    proposal_eval_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    proposal_eval_run.add_argument("--timeout", type=float, default=120)
    proposal_eval_verify = commands.add_parser(
        "verify-agent-proposal-eval",
        help="Re-score proposal evaluation artifacts without model services",
    )
    proposal_eval_verify.add_argument("manifest", type=Path)
    proposal_eval_verify.add_argument("directory", type=Path)
    candidate_eval_freeze = commands.add_parser(
        "freeze-agent-candidate-eval",
        help="Freeze read-then-select action-candidate cases before inference",
    )
    candidate_eval_freeze.add_argument("spec", type=Path)
    candidate_eval_freeze.add_argument("--root", type=Path, required=True)
    candidate_eval_freeze.add_argument("--implementation-root", type=Path)
    candidate_eval_freeze.add_argument("--output", type=Path, required=True)
    candidate_eval_freeze.add_argument("--model", required=True)
    candidate_eval_freeze.add_argument("--model-digest", required=True)
    candidate_eval_freeze.add_argument("--max-steps", type=int, default=3)
    candidate_eval_freeze.add_argument("--max-model-calls", type=int, default=3)
    candidate_eval_freeze.add_argument("--max-tool-calls", type=int, default=1)
    candidate_eval_freeze.add_argument("--max-total-tokens", type=int, default=4096)
    candidate_eval_freeze.add_argument(
        "--max-output-tokens-per-call", type=int, default=256
    )
    candidate_eval_freeze.add_argument("--context-window", type=int, default=8192)
    candidate_eval_freeze.add_argument("--max-seconds", type=float, default=120)
    candidate_eval_freeze.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    candidate_eval_run = commands.add_parser(
        "run-agent-candidate-eval",
        help="Run a frozen read-then-select cohort without executing actions",
    )
    candidate_eval_run.add_argument("manifest", type=Path)
    candidate_eval_run.add_argument("--root", type=Path, required=True)
    candidate_eval_run.add_argument("--implementation-root", type=Path)
    candidate_eval_run.add_argument("--manifest-id", required=True)
    candidate_eval_run.add_argument("--output", type=Path, required=True)
    candidate_eval_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    candidate_eval_run.add_argument("--timeout", type=float, default=120)
    candidate_eval_verify = commands.add_parser(
        "verify-agent-candidate-eval",
        help="Re-score candidate-selection artifacts without model services",
    )
    candidate_eval_verify.add_argument("manifest", type=Path)
    candidate_eval_verify.add_argument("directory", type=Path)
    admission_eval_freeze = commands.add_parser(
        "freeze-agent-admission-eval",
        help="Freeze read-only preparation and deterministic-admission cases",
    )
    admission_eval_freeze.add_argument("spec", type=Path)
    admission_eval_freeze.add_argument("--root", type=Path, required=True)
    admission_eval_freeze.add_argument("--implementation-root", type=Path)
    admission_eval_freeze.add_argument("--output", type=Path, required=True)
    admission_eval_freeze.add_argument("--model", required=True)
    admission_eval_freeze.add_argument("--model-digest", required=True)
    admission_eval_freeze.add_argument("--max-steps", type=int, default=2)
    admission_eval_freeze.add_argument("--max-model-calls", type=int, default=2)
    admission_eval_freeze.add_argument("--max-tool-calls", type=int, default=1)
    admission_eval_freeze.add_argument("--max-total-tokens", type=int, default=2048)
    admission_eval_freeze.add_argument(
        "--max-output-tokens-per-call", type=int, default=256
    )
    admission_eval_freeze.add_argument("--context-window", type=int, default=8192)
    admission_eval_freeze.add_argument("--max-seconds", type=float, default=120)
    admission_eval_freeze.add_argument(
        "--max-observation-chars", type=int, default=20_000
    )
    admission_eval_run = commands.add_parser(
        "run-agent-admission-eval",
        help="Run frozen read-only preparation then deterministic admission",
    )
    admission_eval_run.add_argument("manifest", type=Path)
    admission_eval_run.add_argument("--root", type=Path, required=True)
    admission_eval_run.add_argument("--implementation-root", type=Path)
    admission_eval_run.add_argument("--manifest-id", required=True)
    admission_eval_run.add_argument("--output", type=Path, required=True)
    admission_eval_run.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    admission_eval_run.add_argument("--timeout", type=float, default=120)
    admission_eval_verify = commands.add_parser(
        "verify-agent-admission-eval",
        help="Re-score deterministic-admission artifacts without model services",
    )
    admission_eval_verify.add_argument("manifest", type=Path)
    admission_eval_verify.add_argument("directory", type=Path)

    explanation = commands.add_parser("prepare-project-explanation", help="Export replay-verified project facts without a model")
    explanation.add_argument("report", type=Path)
    explanation.add_argument("--question", required=True)
    explanation.add_argument("--output", type=Path, required=True)
    explanation_check = commands.add_parser("validate-project-explanation", help="Validate exact fact selection against current project evidence")
    explanation_check.add_argument("report", type=Path)
    explanation_check.add_argument("request", type=Path)
    explanation_check.add_argument("answer", type=Path)

    project_review_parser = commands.add_parser(
        "run-project-review",
        help="Answer an engineering question from one project acceptance report",
    )
    project_review_parser.add_argument("report", type=Path)
    project_review_parser.add_argument("--output", type=Path, required=True)
    project_review_parser.add_argument(
        "--claim",
        help="Check one explicit claim; unsupported claims are refused",
    )

    project_comparison_parser = commands.add_parser(
        "compare-projects",
        help="Compare baseline and candidate project acceptance reports",
    )
    project_comparison_parser.add_argument("baseline", type=Path)
    project_comparison_parser.add_argument("candidate", type=Path)
    project_comparison_parser.add_argument("--output", type=Path, required=True)
    comparison_verification_parser = commands.add_parser(
        "verify-project-comparison",
        help="Recompute a saved project comparison and verify its evidence",
    )
    comparison_verification_parser.add_argument("report", type=Path)

    inspect_parser = commands.add_parser("inspect", help="Inspect a supported engineering artifact")
    inspect_parser.add_argument("artifact", type=Path)

    trace_parser = commands.add_parser("trace", help="Trace a signal through a BSW intent model")
    trace_parser.add_argument("intent", type=Path)
    trace_parser.add_argument("signal")

    validate_parser = commands.add_parser("validate-map", help="Validate DBC facts against a BSW intent model")
    validate_parser.add_argument("dbc", type=Path)
    validate_parser.add_argument("intent", type=Path)

    contract_parser = commands.add_parser("validate-contract", help="Validate DBC-to-canonical mappings")
    contract_parser.add_argument("dbc", type=Path)
    contract_parser.add_argument("contract", type=Path)
    contract_parser.add_argument("intent", type=Path)

    suite_parser = commands.add_parser("run-suite", help="Run baseline and fault-injection experiments")
    suite_parser.add_argument("dbc", type=Path)
    suite_parser.add_argument("contract", type=Path)
    suite_parser.add_argument("intent", type=Path)
    suite_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    can_parser = commands.add_parser("run-can-lab", help="Run virtual CAN send/receive and fault experiments")
    can_parser.add_argument("dbc", type=Path)
    can_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    supervision_parser = commands.add_parser("run-can-supervision", help="Run periodic CAN and timeout supervision experiments")
    supervision_parser.add_argument("dbc", type=Path)
    supervision_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    capture_parser = commands.add_parser("capture-log", help="Capture raw CAN frames as can-utils log")
    capture_parser.add_argument("--interface", default="virtual")
    capture_parser.add_argument("--channel", default="workbench")
    capture_parser.add_argument("--count", type=int, default=10)
    capture_parser.add_argument("--timeout", type=float, default=5.0)
    capture_parser.add_argument("--output", type=Path, default=Path("output") / "capture")

    decode_parser = commands.add_parser("decode-log", help="Decode and validate a raw CAN log with a DBC")
    decode_parser.add_argument("log", type=Path)
    decode_parser.add_argument("dbc", type=Path)
    decode_parser.add_argument("--output", type=Path, default=Path("output") / "decode")

    replay_parser = commands.add_parser("replay-log", help="Replay a CAN log to a selected backend")
    replay_parser.add_argument("log", type=Path)
    replay_parser.add_argument("--interface", default="virtual")
    replay_parser.add_argument("--channel", default="workbench")
    replay_parser.add_argument("--gap-ms", type=float)
    replay_parser.add_argument("--output", type=Path, default=Path("output") / "replay")

    log_lab_parser = commands.add_parser("run-log-lab", help="Run capture, decode and replay as one public experiment")
    log_lab_parser.add_argument("dbc", type=Path)
    log_lab_parser.add_argument("--output", type=Path, default=Path("output") / "log-lab")

    probe_parser = commands.add_parser("probe-can-backend", help="Probe a CAN backend without changing the host")
    probe_parser.add_argument("--interface", default="virtual")
    probe_parser.add_argument("--channel", default="workbench")
    probe_parser.add_argument("--output", type=Path, default=Path("output") / "backend-probe")

    backend_lab_parser = commands.add_parser("run-backend-lab", help="Run the same capture/decode/replay contract on a selected backend")
    backend_lab_parser.add_argument("dbc", type=Path)
    backend_lab_parser.add_argument("--interface", default="virtual")
    backend_lab_parser.add_argument("--channel", default="workbench")
    backend_lab_parser.add_argument("--output", type=Path, default=Path("output") / "backend-lab")

    openbsw_patch_parser = commands.add_parser("prepare-openbsw-patch", help="Package local OpenBSW spike changes as evidence")
    openbsw_patch_parser.add_argument("repo", type=Path)
    openbsw_patch_parser.add_argument("--output", type=Path, default=Path("output") / "openbsw-patch")

    uds_lab_parser = commands.add_parser("run-uds-lab", help="Run virtual UDS/ISO-TP diagnostic scenarios")
    uds_lab_parser.add_argument("intent", type=Path)
    uds_lab_parser.add_argument("--interface", default="virtual")
    uds_lab_parser.add_argument("--channel", default="workbench")
    uds_lab_parser.add_argument("--output", type=Path, default=Path("output") / "uds-lab")

    external_parser = commands.add_parser("run-external-ecu", help="Run a build-bound external ECU and bounded diagnostic client")
    external_parser.add_argument("execution", type=Path)
    external_parser.add_argument("--output", type=Path, required=True)
    external_verify = commands.add_parser("verify-external-ecu", help="Verify saved external ECU inventory and diagnostic bindings offline")
    external_verify.add_argument("report", type=Path)

    did_parser = commands.add_parser("read-uds-did", help="Read and verify one DID from an independently running ECU")
    did_parser.add_argument("profile", type=Path)
    did_parser.add_argument("--execution-context", type=Path, help="Optional same-run context captured by the independent executor")
    did_parser.add_argument("--interface", choices=["virtual", "socketcan"], required=True)
    did_parser.add_argument("--channel", required=True)
    did_parser.add_argument("--output", type=Path, required=True)

    uds_probe_parser = commands.add_parser("probe-uds-backend", help="Probe UDS/ISO-TP diagnostic runtime dependencies and backend")
    uds_probe_parser.add_argument("--interface", default="virtual")
    uds_probe_parser.add_argument("--channel", default="workbench")
    uds_probe_parser.add_argument("--output", type=Path, default=Path("output") / "uds-backend-probe")

    dtc_lifecycle_parser = commands.add_parser(
        "run-dtc-lifecycle",
        help="Run deterministic DTC debounce, healing, read and clear experiments",
    )
    dtc_lifecycle_parser.add_argument("intent", type=Path)
    dtc_lifecycle_parser.add_argument(
        "--output", type=Path, default=Path("output") / "dtc-lifecycle"
    )

    dtc_aging_parser = commands.add_parser(
        "run-dtc-aging-lab",
        help="Run explicit DTC operation-cycle, aging and snapshot experiments",
    )
    dtc_aging_parser.add_argument("intent", type=Path)
    dtc_aging_parser.add_argument("--output", type=Path, default=Path("output") / "dtc-aging")

    dtc_reset_parser = commands.add_parser(
        "run-dtc-reset-lab",
        help="Run deterministic DTC hard-reset and persistence experiments",
    )
    dtc_reset_parser.add_argument("intent", type=Path)
    dtc_reset_parser.add_argument("--output", type=Path, default=Path("output") / "dtc-reset")

    dtc_persistence_fault_parser = commands.add_parser(
        "run-dtc-persistence-fault-lab",
        help="Run DTC persistence integrity and flush-failure experiments",
    )
    dtc_persistence_fault_parser.add_argument("intent", type=Path)
    dtc_persistence_fault_parser.add_argument(
        "--output", type=Path, default=Path("output") / "dtc-persistence-fault"
    )

    dtc_redundancy_parser = commands.add_parser(
        "run-dtc-redundancy-lab",
        help="Run DTC redundant-copy generation and recovery experiments",
    )
    dtc_redundancy_parser.add_argument("intent", type=Path)
    dtc_redundancy_parser.add_argument(
        "--output", type=Path, default=Path("output") / "dtc-redundancy"
    )

    dtc_redundancy_repair_parser = commands.add_parser(
        "run-dtc-redundancy-repair-lab",
        help="Run DTC commit-marker, interrupted-write and redundancy-repair experiments",
    )
    dtc_redundancy_repair_parser.add_argument("intent", type=Path)
    dtc_redundancy_repair_parser.add_argument(
        "--output", type=Path, default=Path("output") / "dtc-redundancy-repair"
    )

    review_parser = commands.add_parser(
        "run-review",
        help="Run a local citation-backed retrieval-only engineering review",
    )
    review_parser.add_argument("request", type=Path)
    review_parser.add_argument(
        "--output", type=Path, default=Path("output") / "review"
    )

    review_eval_parser = commands.add_parser(
        "run-review-eval",
        help="Run the deterministic gold engineering-review evaluation",
    )
    review_eval_parser.add_argument("manifest", type=Path)
    review_eval_parser.add_argument(
        "--output", type=Path, default=Path("output") / "review-evaluation"
    )

    communication_parser = commands.add_parser(
        "run-communication-chain",
        help="Bind static DBC/BSW intent paths to deterministic CAN runtime evidence",
    )
    communication_parser.add_argument("dbc", type=Path)
    communication_parser.add_argument("intent", type=Path)
    communication_parser.add_argument("--interface", default="virtual")
    communication_parser.add_argument("--channel")
    communication_parser.add_argument(
        "--output", type=Path, default=Path("output") / "communication-chain"
    )

    communication_delivery_parser = commands.add_parser(
        "run-communication-delivery",
        help="Run, index, verify, and summarize a communication evidence delivery",
    )
    communication_delivery_parser.add_argument("dbc", type=Path)
    communication_delivery_parser.add_argument("intent", type=Path)
    communication_delivery_parser.add_argument("--interface", default="virtual")
    communication_delivery_parser.add_argument("--channel")
    communication_delivery_parser.add_argument("--base", type=Path, default=Path.cwd())
    communication_delivery_parser.add_argument(
        "--output", type=Path, default=Path("output") / "communication-delivery"
    )

    evidence_index_parser = commands.add_parser(
        "index-evidence",
        help="Create a portable manifest for a local evidence bundle",
    )
    evidence_index_parser.add_argument("bundle", type=Path)
    evidence_index_parser.add_argument("--producer", required=True)
    evidence_index_parser.add_argument("--bundle-id")
    evidence_index_parser.add_argument("--base", type=Path, default=Path.cwd())
    evidence_index_parser.add_argument("--manifest", type=Path)

    evidence_verify_parser = commands.add_parser(
        "verify-evidence",
        help="Verify a local evidence bundle against an existing manifest",
    )
    evidence_verify_parser.add_argument("bundle", type=Path)
    evidence_verify_parser.add_argument("manifest", type=Path)
    evidence_verify_parser.add_argument("--base", type=Path, default=Path.cwd())
    evidence_verify_parser.add_argument(
        "--output", type=Path, default=Path("output") / "evidence-verification"
    )

    capsule_parser = commands.add_parser(
        "export-evidence-capsule",
        help="Export a verified communication delivery with local dependency copies",
    )
    capsule_parser.add_argument("delivery", type=Path)
    capsule_parser.add_argument("--base", type=Path, default=Path.cwd())
    capsule_parser.add_argument(
        "--output", type=Path, default=Path("output") / "evidence-capsule"
    )

    capsule_verify_parser = commands.add_parser(
        "verify-evidence-capsule",
        help="Verify the complete inventory and dependency graph of an evidence capsule",
    )
    capsule_verify_parser.add_argument("capsule", type=Path)
    capsule_verify_parser.add_argument(
        "--output", type=Path, default=Path("output") / "evidence-capsule-verification"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "audit-signal-mappings":
            result = audit_mappings(args.source, args.output)
        elif args.command == "inspect-ecuc-project":
            result = run_inspection(args.project, args.output)
        elif args.command == "verify-ecuc-inspection":
            result = verify_inspection(args.report)
        elif args.command == "trace-ecuc-communication":
            result = run_communication(args.project, args.output)
        elif args.command == "verify-ecuc-communication":
            result = verify_communication(args.report)
        elif args.command == "review-ecuc-project":
            result = run_ecuc_review(args.project, args.output, args.application, args.tool_log)
        elif args.command == "verify-ecuc-review":
            result = verify_ecuc_review(args.report)
        elif args.command == "compare-ecuc-reviews":
            result = compare_ecuc_reviews(args.before, args.after, args.output)
        elif args.command == "verify-ecuc-impact":
            result = verify_ecuc_impact(args.report)
        elif args.command == "inspect":
            if args.artifact.suffix.casefold() == ".dbc":
                result = inspect_dbc(args.artifact)
            elif args.artifact.name == "uds_intent.json":
                result = summarize_uds_intent(args.artifact)
            elif args.artifact.name == "dtc_intent.json":
                result = summarize_dtc_intent(args.artifact)
            else:
                result = summarize_issue_report(args.artifact)
        elif args.command in {"import-arxml", "compare-arxml"}:
            result = run_arxml(args.source, args.output, getattr(args, "candidate", None), args.provenance)
        elif args.command == "verify-arxml":
            verify_report(json.loads(args.report.read_text(encoding="utf-8")))
            result = {"status": "passed", "verified": str(args.report)}
        elif args.command == "verify-communication-graph":
            result = verify_graph_report(args.report)
        elif args.command in {"build-communication-graph", "compare-communication-config"}:
            result = run_graph(args.project, args.output, getattr(args, "candidate", None))
        elif args.command == "plan-communication":
            result = preflight_communication(args.dbc, args.intent, args.declaration)
        elif args.command == "run-declared-communication":
            result = run_declared_communication(
                args.dbc, args.intent, args.declaration,
                default_communication_config(args.interface, args.channel), args.output,
            )
        elif args.command == "trace":
            result = trace_signal(args.intent, args.signal).to_dict()
        elif args.command == "validate-map":
            result = validate_dbc_intent(args.dbc, args.intent)
        elif args.command == "validate-contract":
            result = validate_contract_mapping(args.dbc, args.contract, args.intent)
        elif args.command == "run-suite":
            result = run_suite(args.dbc, args.contract, args.intent, args.output)
        elif args.command == "run-can-lab":
            result = run_can_lab(args.dbc, args.output)
        elif args.command == "run-can-supervision":
            result = run_can_supervision(args.dbc, args.output)
        elif args.command == "capture-log":
            config = BusConfig(args.interface, args.channel)
            bus = open_bus(config)
            try:
                result = capture_log(bus, args.output, args.count, args.timeout, config)
            finally:
                bus.shutdown()
        elif args.command == "decode-log":
            result = decode_log(args.log, args.dbc, args.output)
        elif args.command == "replay-log":
            config = BusConfig(args.interface, args.channel)
            bus = open_bus(config)
            try:
                result = replay_log(
                    args.log,
                    bus,
                    timestamps=args.gap_ms is None,
                    gap_s=0.001 if args.gap_ms is None else args.gap_ms / 1000,
                    output=args.output,
                    config=config,
                )
            finally:
                bus.shutdown()
        elif args.command == "run-log-lab":
            result = run_log_lab(args.dbc, args.output)
        elif args.command == "probe-can-backend":
            result = probe_can_backend(BusConfig(args.interface, args.channel), args.output)
        elif args.command == "prepare-openbsw-patch":
            result = prepare_openbsw_patch(args.repo, args.output)
        elif args.command == "run-uds-lab":
            result = run_uds_lab(
                args.intent,
                BusConfig(args.interface, args.channel),
                args.output,
            )
        elif args.command == "verify-ecuc-project":
            from automotive_workbench.project_ecuc import verify
            result = verify(args.report)
        elif args.command == "run-project":
            result = run_project(args.project, args.output, default_communication_config(args.interface, args.channel))
        elif args.command == "explain-project":
            from automotive_workbench.model_explanation import explain
            result = explain(args.report, args.question, args.output, args.model, args.ollama_url,
                             args.knowledge_url, args.knowledge_query, args.timeout)
        elif args.command == "verify-model-explanation":
            from automotive_workbench.model_explanation import verify_explanation
            result = verify_explanation(args.report, args.directory)
        elif args.command == "retrieve-agent-knowledge":
            from automotive_workbench.explanation_services import Endpoint, retrieve_for_agent
            from automotive_workbench.knowledge_policy import load_agent_knowledge_policy
            result = retrieve_for_agent(
                Endpoint(args.knowledge_url, args.timeout),
                args.query,
                load_agent_knowledge_policy(args.policy),
            )
        elif args.command == "run-readonly-agent":
            from automotive_workbench.agent_runtime import (
                AgentBudget,
                AgentRunner,
                build_readonly_registry,
                save_agent_artifact,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.knowledge_policy import (
                load_agent_knowledge_policy,
            )
            from automotive_workbench.model_client import OllamaModelClient

            if (args.knowledge_url is None) != (args.knowledge_policy is None):
                raise ValueError(
                    "--knowledge-url and --knowledge-policy must be supplied together"
                )
            knowledge_endpoint = (
                Endpoint(args.knowledge_url, args.timeout)
                if args.knowledge_url is not None
                else None
            )
            knowledge_policy = (
                load_agent_knowledge_policy(args.knowledge_policy)
                if args.knowledge_policy is not None
                else None
            )
            registry = build_readonly_registry(
                args.report,
                knowledge_endpoint=knowledge_endpoint,
                knowledge_policy=knowledge_policy,
            )
            budget = AgentBudget(
                max_steps=args.max_steps,
                max_model_calls=args.max_model_calls,
                max_tool_calls=args.max_tool_calls,
                max_total_tokens=args.max_total_tokens,
                max_output_tokens_per_call=args.max_output_tokens_per_call,
                context_window=args.context_window,
                max_seconds=args.max_seconds,
                max_observation_chars=args.max_observation_chars,
            )
            trace = AgentRunner(
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                registry,
                budget,
            ).run(
                args.goal,
                args.model,
                pause_after_tool_calls=args.pause_after_tool_calls,
            )
            result = save_agent_artifact(trace, args.output)
        elif args.command == "verify-readonly-agent-trace":
            from automotive_workbench.agent_runtime import verify_agent_trace
            from automotive_workbench.project_explanation import read

            result = verify_agent_trace(read(args.trace))
        elif args.command == "create-agent-evidence-plan":
            from automotive_workbench.agent_evidence_plan import (
                build_agent_evidence_plan,
                save_agent_evidence_plan,
            )

            result = save_agent_evidence_plan(
                build_agent_evidence_plan(args.goal, args.scope), args.output
            )
        elif args.command == "verify-agent-evidence-plan":
            from automotive_workbench.agent_evidence_plan import (
                load_agent_evidence_plan,
                verify_agent_evidence_plan,
            )

            result = verify_agent_evidence_plan(
                load_agent_evidence_plan(args.plan)
            )
        elif args.command == "run-agent-evidence-plan":
            from automotive_workbench.agent_evidence_plan import (
                load_agent_evidence_plan,
                run_agent_evidence_plan,
                save_agent_evidence_plan_result,
            )
            from automotive_workbench.agent_runtime import (
                AgentBudget,
                build_readonly_registry,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.knowledge_policy import (
                load_agent_knowledge_policy,
            )
            from automotive_workbench.model_client import OllamaModelClient

            if (args.knowledge_url is None) != (args.knowledge_policy is None):
                raise ValueError(
                    "--knowledge-url and --knowledge-policy must be supplied together"
                )
            plan = load_agent_evidence_plan(args.plan)
            registry = build_readonly_registry(
                args.report,
                knowledge_endpoint=(
                    Endpoint(args.knowledge_url, args.timeout)
                    if args.knowledge_url is not None
                    else None
                ),
                knowledge_policy=(
                    load_agent_knowledge_policy(args.knowledge_policy)
                    if args.knowledge_policy is not None
                    else None
                ),
            )
            planned = run_agent_evidence_plan(
                plan,
                registry,
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                args.model,
                AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
            result = save_agent_evidence_plan_result(
                plan, planned, args.output
            )
        elif args.command == "verify-agent-evidence-plan-result":
            from automotive_workbench.agent_evidence_plan import (
                load_agent_evidence_plan,
                verify_agent_evidence_plan_result,
            )
            from automotive_workbench.project_explanation import read

            result = verify_agent_evidence_plan_result(
                load_agent_evidence_plan(args.plan), read(args.result)
            )
        elif args.command == "run-agent-evidence-summary":
            from automotive_workbench.agent_evidence_plan import (
                load_agent_evidence_plan,
            )
            from automotive_workbench.agent_evidence_summary import (
                run_agent_evidence_summary,
                save_agent_evidence_summary_result,
            )
            from automotive_workbench.agent_runtime import (
                AgentBudget,
                build_readonly_registry,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.knowledge_policy import (
                load_agent_knowledge_policy,
            )
            from automotive_workbench.model_client import OllamaModelClient

            if (args.knowledge_url is None) != (args.knowledge_policy is None):
                raise ValueError(
                    "--knowledge-url and --knowledge-policy must be supplied together"
                )
            plan = load_agent_evidence_plan(args.plan)
            registry = build_readonly_registry(
                args.report,
                knowledge_endpoint=(
                    Endpoint(args.knowledge_url, args.timeout)
                    if args.knowledge_url is not None
                    else None
                ),
                knowledge_policy=(
                    load_agent_knowledge_policy(args.knowledge_policy)
                    if args.knowledge_policy is not None
                    else None
                ),
            )
            summarized = run_agent_evidence_summary(
                plan,
                registry,
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                args.model,
                AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
            result = save_agent_evidence_summary_result(
                plan, summarized, args.output
            )
        elif args.command == "verify-agent-evidence-summary-result":
            from automotive_workbench.agent_evidence_plan import (
                load_agent_evidence_plan,
            )
            from automotive_workbench.agent_evidence_summary import (
                load_agent_evidence_summary_result,
                verify_agent_evidence_summary_result,
            )

            result = verify_agent_evidence_summary_result(
                load_agent_evidence_plan(args.plan),
                load_agent_evidence_summary_result(args.result),
            )
        elif args.command == "create-agent-evidence-pair-plan":
            from automotive_workbench.agent_evidence_pair_summary import (
                build_agent_evidence_pair_plan,
                save_agent_evidence_pair_plan,
            )

            result = save_agent_evidence_pair_plan(
                build_agent_evidence_pair_plan(args.goal, args.check_ids),
                args.output,
            )
        elif args.command == "verify-agent-evidence-pair-plan":
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
                verify_agent_evidence_pair_plan,
            )

            result = verify_agent_evidence_pair_plan(
                load_agent_evidence_pair_plan(args.plan)
            )
        elif args.command in {"run-agent-evidence-pair-summary", "run-agent-evidence-pair-summary-v06"}:
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
                run_agent_evidence_pair_summary,
                save_agent_evidence_pair_summary_result,
            )
            from automotive_workbench.agent_runtime import AgentBudget
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            plan = load_agent_evidence_pair_plan(args.plan)
            summarized = run_agent_evidence_pair_summary(
                args.report,
                plan,
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                args.model,
                AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
                requirement_text_projection=args.command.endswith("-v06"),
            )
            result = save_agent_evidence_pair_summary_result(
                args.report, plan, summarized, args.output
            )
        elif args.command in {"verify-agent-evidence-pair-summary-result", "verify-agent-evidence-pair-summary-result-v06"}:
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
                load_agent_evidence_pair_summary_result,
                verify_agent_evidence_pair_summary_result,
            )

            saved_result = load_agent_evidence_pair_summary_result(args.result)
            if args.command.endswith("-v06") and saved_result.get("schema_version") != "agent-evidence-pair-summary-result-0.6":
                raise ValueError("Expected Agent evidence-pair summary v0.6 result")
            result = verify_agent_evidence_pair_summary_result(
                args.report,
                load_agent_evidence_pair_plan(args.plan),
                saved_result,
            )
        elif args.command == "run-agent-evidence-pair-summary-v04":
            from automotive_workbench.agent_evidence_pair_summary_v04 import (
                run_agent_evidence_pair_summary_v04,
                save_agent_evidence_pair_summary_result_v04,
            )
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
            )
            from automotive_workbench.agent_runtime import AgentBudget
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            plan = load_agent_evidence_pair_plan(args.plan)
            summarized = run_agent_evidence_pair_summary_v04(
                args.report,
                plan,
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                args.model,
                AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
            result = save_agent_evidence_pair_summary_result_v04(
                args.report, plan, summarized, args.output
            )
        elif args.command == "verify-agent-evidence-pair-summary-result-v04":
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
            )
            from automotive_workbench.agent_evidence_pair_summary_v04 import (
                load_agent_evidence_pair_summary_result_v04,
                verify_agent_evidence_pair_summary_result_v04,
            )

            result = verify_agent_evidence_pair_summary_result_v04(
                args.report,
                load_agent_evidence_pair_plan(args.plan),
                load_agent_evidence_pair_summary_result_v04(args.result),
            )
        elif args.command == "render-agent-evidence-pairs-v05":
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
            )
            from automotive_workbench.agent_evidence_pair_summary_v04 import (
                load_agent_evidence_pair_summary_result_v04,
            )
            from automotive_workbench.agent_evidence_pair_presentation_v05 import (
                build_agent_evidence_pair_presentation_v05,
                save_agent_evidence_pair_presentation_v05,
            )

            plan = load_agent_evidence_pair_plan(args.plan)
            rendered = build_agent_evidence_pair_presentation_v05(
                args.report,
                plan,
                load_agent_evidence_pair_summary_result_v04(args.source_result),
            )
            result = save_agent_evidence_pair_presentation_v05(
                args.report, plan, rendered, args.output
            )
        elif args.command == "verify-agent-evidence-pairs-v05":
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
            )
            from automotive_workbench.agent_evidence_pair_presentation_v05 import (
                load_agent_evidence_pair_presentation_v05,
                verify_agent_evidence_pair_presentation_v05,
            )

            result = verify_agent_evidence_pair_presentation_v05(
                args.report,
                load_agent_evidence_pair_plan(args.plan),
                load_agent_evidence_pair_presentation_v05(args.result),
            )
        elif args.command == "render-agent-evidence-pairs-v06":
            from automotive_workbench.agent_evidence_pair_summary import (
                load_agent_evidence_pair_plan,
                load_agent_evidence_pair_summary_result,
            )
            from automotive_workbench.agent_evidence_pair_presentation_v06 import (
                build_agent_evidence_pair_presentation_v06,
                save_agent_evidence_pair_presentation_v06,
            )

            plan = load_agent_evidence_pair_plan(args.plan)
            rendered = build_agent_evidence_pair_presentation_v06(
                args.report, plan, load_agent_evidence_pair_summary_result(args.source_result)
            )
            result = save_agent_evidence_pair_presentation_v06(
                args.report, plan, rendered, args.output
            )
        elif args.command == "verify-agent-evidence-pairs-v06":
            from automotive_workbench.agent_evidence_pair_summary import load_agent_evidence_pair_plan
            from automotive_workbench.agent_evidence_pair_presentation_v06 import (
                load_agent_evidence_pair_presentation_v06,
                verify_agent_evidence_pair_presentation_v06,
            )

            result = verify_agent_evidence_pair_presentation_v06(
                args.report, load_agent_evidence_pair_plan(args.plan),
                load_agent_evidence_pair_presentation_v06(args.result),
            )
        elif args.command == "assess-agent-evidence-pair-model-v07":
            from automotive_workbench.agent_evidence_pair_summary import load_agent_evidence_pair_plan
            from automotive_workbench.agent_evidence_pair_coverage_v07 import (
                assess_agent_evidence_pair_model_v07,
                save_agent_evidence_pair_model_coverage_v07,
            )

            plan = load_agent_evidence_pair_plan(args.plan)
            assessed = assess_agent_evidence_pair_model_v07(
                args.report, plan, args.presentation
            )
            result = save_agent_evidence_pair_model_coverage_v07(
                args.report, plan, args.presentation, assessed, args.output
            )
        elif args.command == "verify-agent-evidence-pair-model-v07":
            from automotive_workbench.agent_evidence_pair_summary import load_agent_evidence_pair_plan
            from automotive_workbench.agent_evidence_pair_coverage_v07 import (
                load_agent_evidence_pair_model_coverage_v07,
                verify_agent_evidence_pair_model_coverage_v07,
            )

            result = verify_agent_evidence_pair_model_coverage_v07(
                args.report, load_agent_evidence_pair_plan(args.plan),
                args.presentation, load_agent_evidence_pair_model_coverage_v07(args.result),
            )
        elif args.command == "freeze-agent-evidence-comparison":
            from automotive_workbench.agent_evidence_comparison import (
                freeze_agent_evidence_comparison,
            )
            from automotive_workbench.agent_runtime import AgentBudget

            result = freeze_agent_evidence_comparison(
                args.root,
                args.implementation_root,
                args.spec,
                args.output,
                model=args.model,
                model_digest=args.model_digest,
                budget=AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
                knowledge_policy_path=args.knowledge_policy,
                knowledge_corpus_path=args.knowledge_corpus,
            )
        elif args.command == "verify-agent-evidence-comparison-manifest":
            from automotive_workbench.agent_evidence_comparison import (
                load_agent_evidence_comparison_manifest,
                verify_agent_evidence_comparison_manifest,
            )

            result = verify_agent_evidence_comparison_manifest(
                load_agent_evidence_comparison_manifest(args.manifest)
            )
        elif args.command == "verify-agent-evidence-comparison":
            from automotive_workbench.agent_evidence_comparison import (
                verify_agent_evidence_comparison,
            )

            result = verify_agent_evidence_comparison(
                args.manifest, args.directory
            )
        elif args.command == "verify-readonly-agent-checkpoint":
            from automotive_workbench.agent_runtime import verify_agent_checkpoint
            from automotive_workbench.project_explanation import read

            result = verify_agent_checkpoint(read(args.checkpoint))
        elif args.command == "resume-readonly-agent":
            from automotive_workbench.agent_runtime import (
                AgentBudget,
                AgentRunner,
                build_readonly_registry,
                resume_agent_idempotent,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.knowledge_policy import (
                load_agent_knowledge_policy,
            )
            from automotive_workbench.model_client import OllamaModelClient
            from automotive_workbench.project_explanation import read

            if (args.knowledge_url is None) != (args.knowledge_policy is None):
                raise ValueError(
                    "--knowledge-url and --knowledge-policy must be supplied together"
                )
            checkpoint = read(args.checkpoint)
            knowledge_endpoint = (
                Endpoint(args.knowledge_url, args.timeout)
                if args.knowledge_url is not None
                else None
            )
            knowledge_policy = (
                load_agent_knowledge_policy(args.knowledge_policy)
                if args.knowledge_policy is not None
                else None
            )
            registry = build_readonly_registry(
                args.report,
                knowledge_endpoint=knowledge_endpoint,
                knowledge_policy=knowledge_policy,
            )
            result = resume_agent_idempotent(
                AgentRunner(
                    OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                    registry,
                    AgentBudget(**checkpoint["budget"]),
                ),
                checkpoint,
                args.output,
                pause_after_tool_calls=args.pause_after_tool_calls,
            )
        elif args.command == "verify-readonly-agent-resume":
            from automotive_workbench.agent_runtime import (
                verify_agent_resume_result,
            )
            from automotive_workbench.project_explanation import read

            result = verify_agent_resume_result(
                read(args.checkpoint), read(args.result)
            )
        elif args.command == "issue-agent-action-candidate":
            from automotive_workbench.agent_action_candidate import (
                issue_action_candidate,
                save_action_candidate,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            candidate = issue_action_candidate(
                checkpoint,
                tool_name=args.tool_name,
                arguments=read(args.arguments),
                evidence_ids=args.evidence_id,
            )
            result = save_action_candidate(
                checkpoint, candidate, args.output
            )
        elif args.command == "verify-agent-action-candidate":
            from automotive_workbench.agent_action_candidate import (
                load_and_verify_action_candidate,
            )

            result = load_and_verify_action_candidate(
                args.checkpoint, args.candidate
            )
        elif args.command == "select-agent-action-candidate":
            from automotive_workbench.agent_action_candidate import (
                CandidateSelectionRunner,
                save_candidate_selection,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            candidates = [read(path) for path in args.candidate]
            selection = CandidateSelectionRunner(
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout))
            ).run(checkpoint, candidates)
            result = save_candidate_selection(
                checkpoint, candidates, selection, args.output
            )
        elif args.command == "verify-agent-candidate-selection":
            from automotive_workbench.agent_action_candidate import (
                load_and_verify_candidate_selection,
            )

            result = load_and_verify_candidate_selection(
                args.checkpoint, args.candidate, args.selection
            )
        elif args.command == "request-agent-approval-from-candidate":
            from automotive_workbench.agent_action_candidate import (
                build_approval_request_from_candidate_selection,
            )
            from automotive_workbench.agent_approval import (
                save_agent_approval_request,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            candidates = [read(path) for path in args.candidate]
            selection = read(args.selection)
            created_at = datetime.now(timezone.utc)
            request = build_approval_request_from_candidate_selection(
                checkpoint,
                candidates,
                selection,
                reason=args.reason,
                created_at=created_at,
                expires_at=created_at
                + timedelta(seconds=args.expires_in_seconds),
            )
            result = save_agent_approval_request(
                checkpoint, request, args.output
            )
        elif args.command == "verify-agent-approval-from-candidate":
            from automotive_workbench.agent_action_candidate import (
                verify_approval_request_from_candidate_selection,
            )
            from automotive_workbench.project_explanation import read

            result = verify_approval_request_from_candidate_selection(
                read(args.checkpoint),
                [read(path) for path in args.candidate],
                read(args.selection),
                read(args.request),
            )
        elif args.command == "issue-agent-action-intent":
            from automotive_workbench.agent_action_admission import (
                issue_action_intent,
                save_action_intent,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            intent = issue_action_intent(checkpoint, read(args.spec))
            result = save_action_intent(checkpoint, intent, args.output)
        elif args.command == "verify-agent-action-intent":
            from automotive_workbench.agent_action_admission import (
                load_and_verify_action_intent,
            )

            result = load_and_verify_action_intent(args.checkpoint, args.intent)
        elif args.command == "admit-agent-action-candidates":
            from automotive_workbench.agent_action_admission import (
                admit_action_candidates,
                save_action_admission,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            intent = read(args.intent)
            candidates = [read(path) for path in args.candidate]
            admission = admit_action_candidates(checkpoint, intent, candidates)
            result = save_action_admission(
                checkpoint, intent, candidates, admission, args.output
            )
        elif args.command == "verify-agent-action-admission":
            from automotive_workbench.agent_action_admission import (
                load_and_verify_action_admission,
            )

            result = load_and_verify_action_admission(
                args.checkpoint, args.intent, args.candidate, args.admission
            )
        elif args.command == "request-agent-approval-from-admission":
            from automotive_workbench.agent_action_admission import (
                build_approval_request_from_admission,
            )
            from automotive_workbench.agent_approval import (
                save_agent_approval_request,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            created_at = datetime.now(timezone.utc)
            request = build_approval_request_from_admission(
                checkpoint,
                read(args.intent),
                [read(path) for path in args.candidate],
                read(args.admission),
                reason=args.reason,
                created_at=created_at,
                expires_at=created_at
                + timedelta(seconds=args.expires_in_seconds),
            )
            result = save_agent_approval_request(
                checkpoint, request, args.output
            )
        elif args.command == "verify-agent-approval-from-admission":
            from automotive_workbench.agent_action_admission import (
                verify_approval_request_from_admission,
            )
            from automotive_workbench.project_explanation import read

            result = verify_approval_request_from_admission(
                read(args.checkpoint),
                read(args.intent),
                [read(path) for path in args.candidate],
                read(args.admission),
                read(args.request),
            )
        elif args.command == "propose-agent-action":
            from automotive_workbench.agent_proposal import (
                ActionProposalRunner,
                save_action_proposal,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            proposal = ActionProposalRunner(
                OllamaModelClient(Endpoint(args.ollama_url, args.timeout))
            ).run(checkpoint)
            result = save_action_proposal(checkpoint, proposal, args.output)
        elif args.command == "verify-agent-action-proposal":
            from automotive_workbench.agent_proposal import (
                load_and_verify_action_proposal,
            )

            result = load_and_verify_action_proposal(
                args.checkpoint, args.proposal
            )
        elif args.command == "request-agent-approval-from-proposal":
            from automotive_workbench.agent_approval import (
                save_agent_approval_request,
            )
            from automotive_workbench.agent_proposal import (
                build_approval_request_from_proposal,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            proposal = read(args.proposal)
            created_at = datetime.now(timezone.utc)
            request = build_approval_request_from_proposal(
                checkpoint,
                proposal,
                reason=args.reason,
                created_at=created_at,
                expires_at=created_at
                + timedelta(seconds=args.expires_in_seconds),
            )
            result = save_agent_approval_request(
                checkpoint, request, args.output
            )
        elif args.command == "request-agent-approval":
            from automotive_workbench.agent_approval import (
                build_agent_approval_request,
                save_agent_approval_request,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            arguments = read(args.arguments)
            created_at = datetime.now(timezone.utc)
            request = build_agent_approval_request(
                checkpoint,
                tool_name=args.tool_name,
                permission=args.permission,
                arguments=arguments,
                reason=args.reason,
                evidence_ids=args.evidence_id,
                created_at=created_at,
                expires_at=created_at
                + timedelta(seconds=args.expires_in_seconds),
            )
            result = save_agent_approval_request(
                checkpoint, request, args.output
            )
        elif args.command == "decide-agent-approval":
            from automotive_workbench.agent_approval import (
                build_agent_approval_decision,
                save_agent_approval_decision,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            request = read(args.request)
            decision = build_agent_approval_decision(
                checkpoint,
                request,
                status=args.decision,
                decided_at=_utc_now_at_or_after(request["created_at"]),
                actor_id=args.actor,
                reason=args.reason,
            )
            result = save_agent_approval_decision(
                checkpoint, request, decision, args.output
            )
        elif args.command == "expire-agent-approval":
            from automotive_workbench.agent_approval import (
                build_agent_approval_decision,
                save_agent_approval_decision,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            request = read(args.request)
            decision = build_agent_approval_decision(
                checkpoint,
                request,
                status="expired",
                decided_at=datetime.now(timezone.utc),
                reason="request_expired",
            )
            result = save_agent_approval_decision(
                checkpoint, request, decision, args.output
            )
        elif args.command == "verify-agent-approval-request":
            from automotive_workbench.agent_approval import (
                load_and_verify_agent_approval,
            )

            result = load_and_verify_agent_approval(
                args.checkpoint, args.request
            )
        elif args.command == "verify-agent-approval-decision":
            from automotive_workbench.agent_approval import (
                load_and_verify_agent_approval,
            )

            result = load_and_verify_agent_approval(
                args.checkpoint, args.request, args.decision
            )
        elif args.command == "claim-agent-approval":
            from automotive_workbench.agent_transaction import (
                claim_agent_approval,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            request = read(args.request)
            decision = read(args.decision)
            result = claim_agent_approval(
                checkpoint,
                request,
                decision,
                args.ledger,
                claimed_at=_utc_now_at_or_after(decision["decided_at"]),
            )
        elif args.command == "complete-agent-transaction":
            from automotive_workbench.agent_transaction import (
                complete_agent_transaction,
                transaction_paths,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            request = read(args.request)
            decision = read(args.decision)
            claim_path, _ = transaction_paths(
                args.ledger, checkpoint, request
            )
            claim = read(claim_path)
            result = complete_agent_transaction(
                checkpoint,
                request,
                decision,
                args.ledger,
                status=args.outcome,
                reason=args.reason,
                completed_at=_utc_now_at_or_after(claim["claimed_at"]),
            )
        elif args.command == "verify-agent-transaction":
            from automotive_workbench.agent_transaction import (
                load_and_verify_agent_transaction,
            )

            result = load_and_verify_agent_transaction(
                args.checkpoint,
                args.request,
                args.decision,
                args.ledger,
            )
        elif args.command == "execute-agent-virtual-can":
            from automotive_workbench.agent_transaction import transaction_paths
            from automotive_workbench.agent_virtual_execution import (
                execute_agent_virtual_can,
            )
            from automotive_workbench.project_explanation import read

            checkpoint = read(args.checkpoint)
            request = read(args.request)
            decision = read(args.decision)
            started_at = datetime.now(timezone.utc)
            if args.enable_virtual_execution:
                claim_path, _ = transaction_paths(
                    args.ledger, checkpoint, request
                )
                claim = read(claim_path)
                started_at = _utc_now_at_or_after(claim["claimed_at"])
            result = execute_agent_virtual_can(
                checkpoint,
                request,
                decision,
                args.ledger,
                enabled=args.enable_virtual_execution,
                started_at=started_at,
            )
        elif args.command == "verify-agent-virtual-execution":
            from automotive_workbench.agent_virtual_execution import (
                load_and_verify_virtual_execution,
            )

            result = load_and_verify_virtual_execution(
                args.checkpoint,
                args.request,
                args.decision,
                args.ledger,
            )
        elif args.command == "freeze-readonly-agent-eval":
            from automotive_workbench.agent_evaluation import (
                freeze_agent_evaluation,
            )
            from automotive_workbench.agent_runtime import AgentBudget

            result = freeze_agent_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.spec,
                args.output,
                model=args.model,
                model_digest=args.model_digest,
                budget=AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
                knowledge_policy_path=args.knowledge_policy,
            )
        elif args.command == "run-readonly-agent-eval":
            from automotive_workbench.agent_evaluation import run_agent_evaluation
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            result = run_agent_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.manifest,
                args.manifest_id,
                args.output,
                client=OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
                knowledge_endpoint=(
                    Endpoint(args.knowledge_url, args.timeout)
                    if args.knowledge_url is not None
                    else None
                ),
            )
        elif args.command == "verify-readonly-agent-eval":
            from automotive_workbench.agent_evaluation import (
                verify_agent_evaluation,
            )

            result = verify_agent_evaluation(args.manifest, args.directory)
        elif args.command == "prepare-agent-human-review":
            from automotive_workbench.agent_human_review import (
                prepare_agent_human_review,
            )

            result = prepare_agent_human_review(
                args.implementation_root,
                args.manifest,
                args.evaluation_directory,
                args.output,
            )
        elif args.command == "verify-agent-human-review":
            from automotive_workbench.agent_human_review import (
                verify_agent_human_review,
            )

            result = verify_agent_human_review(
                args.implementation_root,
                args.manifest,
                args.evaluation_directory,
                args.directory,
            )
        elif args.command == "finalize-agent-human-review":
            from automotive_workbench.agent_human_review import (
                finalize_agent_human_review,
            )

            result = finalize_agent_human_review(
                args.pack, args.draft, args.output
            )
        elif args.command == "verify-agent-human-review-assessment":
            from automotive_workbench.agent_human_review import (
                verify_agent_human_review_assessment,
            )

            result = verify_agent_human_review_assessment(
                args.pack, args.assessment
            )
        elif args.command == "freeze-agent-proposal-eval":
            from automotive_workbench.agent_proposal_evaluation import (
                freeze_agent_proposal_evaluation,
            )
            from automotive_workbench.agent_runtime import AgentBudget

            result = freeze_agent_proposal_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.spec,
                args.output,
                model=args.model,
                model_digest=args.model_digest,
                budget=AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
        elif args.command == "run-agent-proposal-eval":
            from automotive_workbench.agent_proposal_evaluation import (
                run_agent_proposal_evaluation,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            result = run_agent_proposal_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.manifest,
                args.manifest_id,
                args.output,
                client=OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
            )
        elif args.command == "verify-agent-proposal-eval":
            from automotive_workbench.agent_proposal_evaluation import (
                verify_agent_proposal_evaluation,
            )

            result = verify_agent_proposal_evaluation(
                args.manifest, args.directory
            )
        elif args.command == "freeze-agent-candidate-eval":
            from automotive_workbench.agent_candidate_evaluation import (
                freeze_agent_candidate_evaluation,
            )
            from automotive_workbench.agent_runtime import AgentBudget

            result = freeze_agent_candidate_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.spec,
                args.output,
                model=args.model,
                model_digest=args.model_digest,
                budget=AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
        elif args.command == "run-agent-candidate-eval":
            from automotive_workbench.agent_candidate_evaluation import (
                run_agent_candidate_evaluation,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            result = run_agent_candidate_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.manifest,
                args.manifest_id,
                args.output,
                client=OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
            )
        elif args.command == "verify-agent-candidate-eval":
            from automotive_workbench.agent_candidate_evaluation import (
                verify_agent_candidate_evaluation,
            )

            result = verify_agent_candidate_evaluation(
                args.manifest, args.directory
            )
        elif args.command == "freeze-agent-admission-eval":
            from automotive_workbench.agent_admission_evaluation import (
                freeze_agent_admission_evaluation,
            )
            from automotive_workbench.agent_runtime import AgentBudget

            result = freeze_agent_admission_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.spec,
                args.output,
                model=args.model,
                model_digest=args.model_digest,
                budget=AgentBudget(
                    max_steps=args.max_steps,
                    max_model_calls=args.max_model_calls,
                    max_tool_calls=args.max_tool_calls,
                    max_total_tokens=args.max_total_tokens,
                    max_output_tokens_per_call=args.max_output_tokens_per_call,
                    context_window=args.context_window,
                    max_seconds=args.max_seconds,
                    max_observation_chars=args.max_observation_chars,
                ),
            )
        elif args.command == "run-agent-admission-eval":
            from automotive_workbench.agent_admission_evaluation import (
                run_agent_admission_evaluation,
            )
            from automotive_workbench.explanation_services import Endpoint
            from automotive_workbench.model_client import OllamaModelClient

            result = run_agent_admission_evaluation(
                args.root,
                args.implementation_root or args.root,
                args.manifest,
                args.manifest_id,
                args.output,
                client=OllamaModelClient(Endpoint(args.ollama_url, args.timeout)),
            )
        elif args.command == "verify-agent-admission-eval":
            from automotive_workbench.agent_admission_evaluation import (
                verify_agent_admission_evaluation,
            )

            result = verify_agent_admission_evaluation(
                args.manifest, args.directory
            )
        elif args.command == "prepare-project-explanation":
            from automotive_workbench.project_explanation import prepare
            result = prepare(args.report, args.question, args.output)
        elif args.command == "validate-project-explanation":
            from automotive_workbench.project_explanation import validate_answer
            result = validate_answer(args.report, args.request, args.answer)
        elif args.command == "run-project-review":
            result = run_project_review(args.report, args.output, args.claim)
        elif args.command == "list-engineering-questions":
            result = catalog()
        elif args.command == "search-engineering-questions":
            result = search_questions(args.query, args.limit, args.input_version)
        elif args.command == "review-engineering":
            result = run_engineering_review(args.report, args.question, args.output)
        elif args.command == "verify-engineering-review":
            result = verify_engineering_review(args.report)
        elif args.command == "verify-project-comparison":
            result = validate_project_comparison(args.report)
        elif args.command == "compare-projects":
            result = compare_project_reports(
                args.baseline, args.candidate, args.output
            )
        elif args.command == "run-external-ecu":
            result = run_external_ecu(args.execution, args.output)
        elif args.command == "verify-external-ecu":
            result = verify_external_ecu(args.report)
        elif args.command == "read-uds-did":
            from automotive_workbench.external_ecu import read_json as read_external_json

            context = read_external_json(args.execution_context) if args.execution_context else None
            result = read_uds_did(args.profile, BusConfig(args.interface, args.channel), args.output, **({"execution_context": context} if context is not None else {}))
        elif args.command == "probe-uds-backend":
            result = probe_uds_backend(BusConfig(args.interface, args.channel), args.output)
        elif args.command == "run-dtc-lifecycle":
            result = run_dtc_lifecycle(args.intent, args.output)
        elif args.command == "run-dtc-aging-lab":
            result = run_dtc_aging_lab(args.intent, args.output)
        elif args.command == "run-dtc-reset-lab":
            result = run_dtc_reset_lab(args.intent, args.output)
        elif args.command == "run-dtc-persistence-fault-lab":
            result = run_dtc_persistence_fault_lab(args.intent, args.output)
        elif args.command == "run-dtc-redundancy-lab":
            result = run_dtc_redundancy_lab(args.intent, args.output)
        elif args.command == "run-dtc-redundancy-repair-lab":
            result = run_dtc_redundancy_repair_lab(args.intent, args.output)
        elif args.command == "run-review":
            result = run_review(args.request, args.output)
        elif args.command == "run-review-eval":
            result = run_review_evaluation(args.manifest, args.output)
        elif args.command == "run-communication-chain":
            result = run_communication_chain(
                args.dbc,
                args.intent,
                args.output,
                default_communication_config(args.interface, args.channel),
            )
        elif args.command == "run-communication-delivery":
            result = run_communication_delivery(
                args.dbc,
                args.intent,
                args.output,
                default_communication_config(args.interface, args.channel),
                base=args.base,
            )
        elif args.command == "index-evidence":
            manifest_path = args.manifest or (
                args.bundle.parent / f"{args.bundle.name}.evidence-manifest.json"
            )
            result = create_evidence_bundle_manifest(
                args.bundle,
                manifest_path,
                args.producer,
                bundle_id=args.bundle_id,
                base=args.base,
            )
        elif args.command == "verify-evidence":
            result = verify_evidence_bundle(
                args.bundle,
                args.manifest,
                args.output,
                base=args.base,
            )
        elif args.command == "export-evidence-capsule":
            result = export_evidence_capsule(
                args.delivery,
                args.output,
                base=args.base,
            )
        elif args.command == "verify-evidence-capsule":
            result = verify_evidence_capsule(args.capsule, args.output)
        else:
            result = run_backend_lab(
                args.dbc,
                BusConfig(args.interface, args.channel),
                args.output,
            )
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        _print_json({"status": "error", "message": str(exc)})
        return 1
    _print_json(result)
    exit_status = result.get("status", result.get("protocol_status"))
    if exit_status in {"attention-required", "no-paths"}:
        return 2
    if exit_status in {
        "failed",
        "partial",
        "unassessed",
        "refused",
        "regressed",
        "changed",
        "not-comparable",
    }:
        return 2
    if exit_status == "blocked":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
