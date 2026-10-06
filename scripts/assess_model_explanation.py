"""Freeze evidence-bound questions before inference; score citations, never prose.

No target execution or downloads. Local evidence paths are resolved under --root.
The frozen manifest hash must be supplied separately to run an assessment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from automotive_workbench.model_explanation import PROMPT_VERSION, explain, select_facts, verify_explanation
from automotive_workbench.project_explanation import build_request, canonical, digest, read


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def resolve(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts or path.is_symlink():
        raise ValueError("Evidence path must be relative and contained")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence escapes root")
    return path


def bundle_digest(report: Path) -> str:
    files = {}
    for path in sorted(report.parent.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink evidence is unsupported")
        if path.is_file():
            files[path.relative_to(report.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest(files)


def implementation_digest(root: Path) -> str:
    paths = ["src/automotive_workbench/" + name for name in
             ("model_explanation.py", "explanation_services.py", "project_explanation.py")]
    paths.append("scripts/assess_model_explanation.py")
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths})


def gold_ids(request: dict, gold: list) -> list[str]:
    found = []
    for expected in gold:
        matches = [f["fact_id"] for f in request["facts"]
                   if all(canonical(f[k]) == canonical(v) for k, v in expected.items())]
        if len(matches) != 1:
            raise ValueError("Gold must identify exactly one replayed fact: " + canonical(expected))
        found.append(matches[0])
    if len(set(found)) != len(found):
        raise ValueError("Duplicate gold fact")
    return found


def score(case: dict, result: dict, context: dict) -> dict:
    required = set(case["gold_fact_ids"])
    available = {f["fact_id"] for f in context["facts"]}
    answer = result.get("answer") or {}
    selected = {f["fact_id"] for f in answer.get("project_facts", [])}
    # A guard rejection is not a model refusal. Empty gold has no recall score.
    refusal = result["status"] == "unassessed" and answer.get("answer_status") == "unassessed"
    return {"adapter_status": result["status"], "reason": result["reason"],
            "required_facts": len(required), "context_facts": len(required & available),
            "cited_required_facts": len(required & selected),
            "gold_recall": len(required & selected) / len(required) if required else None,
            "structured_task_passed": (result["status"] == "passed" and required <= selected) if required else refusal,
            "model_declared_insufficient": refusal,
            "guard_rejected_output": result["status"] == "refused",
            "manual_sources": len(context["manuals"]),
            "validated_manual_quotes": len(answer.get("manual_quotes", [])),
            "manual_relevance": "unassessed", "prose_correctness": "unassessed",
            "human_usability": "unassessed", "elapsed_ms": result["elapsed_ms"],
            "gaps": result["gaps"]}


def freeze(root: Path, spec: Path, output: Path, model: str, model_digest: str) -> dict:
    if output.exists():
        raise ValueError("Freeze output must be absent")
    specification = read(spec)
    cases = []
    for item in specification["cases"]:
        report = resolve(root, item["report"])
        entry = {**item, "bundle_sha256": bundle_digest(report)}
        try:
            request = build_request(report, item["question"])
        except ValueError as exc:
            if item["expectation"] != "preflight_rejection":
                raise
            entry.update(preflight_error=str(exc), gold_fact_ids=[])
        else:
            if item["expectation"] == "preflight_rejection":
                raise ValueError("Negative evidence unexpectedly verified")
            ids = gold_ids(request, item["gold"])
            entry.update(request_id=request["request_id"], gold_fact_ids=ids,
                         context_gold_count=len(set(ids) & {f["fact_id"] for f in select_facts(request)}))
        cases.append(entry)
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate case id")
    manifest = {"version": "p30-assessment-0.1", "cohort": specification["cohort"],
                "spec_sha256": digest(specification), "implementation_sha256": implementation_digest(root),
                "prompt_version": PROMPT_VERSION, "model": model, "model_digest": model_digest,
                "cases": cases, "boundary": "Agent-authored frozen questions; not independent human gold or semantic certification."}
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, manifest)
    return {"manifest_sha256": digest(manifest), "cases": len(cases)}


def assess(root: Path, manifest_path: Path, expected_hash: str, output: Path,
           ollama_url: str, knowledge_url: str | None) -> dict:
    manifest = read(manifest_path)
    if digest(manifest) != expected_hash or implementation_digest(root) != manifest["implementation_sha256"]:
        raise ValueError("Frozen manifest or implementation changed")
    if output.exists():
        raise ValueError("Assessment output must be absent; never overwrite a trial")
    # Check the entire cohort before any model call.
    for case in manifest["cases"]:
        if bundle_digest(resolve(root, case["report"])) != case["bundle_sha256"]:
            raise ValueError("Frozen evidence changed: " + case["id"])
    output.mkdir(parents=True)
    rows = []
    for case in manifest["cases"]:
        report = resolve(root, case["report"])
        if case["expectation"] == "preflight_rejection":
            try:
                build_request(report, case["question"])
            except ValueError as exc:
                if str(exc) != case["preflight_error"]:
                    raise ValueError("Preflight rejection changed") from exc
                rows.append({"case": case["id"], "mode": "preflight", "status": "rejected_before_inference",
                             "reason": str(exc), "model_called": False})
            else:
                raise ValueError("Historical evidence unexpectedly accepted")
        else:
            request = build_request(report, case["question"])
            if request["request_id"] != case["request_id"]:
                raise ValueError("Frozen request changed")
            for mode in (["project", "retrieval"] if knowledge_url else ["project"]):
                destination = output / (case["id"] + "-" + mode)
                result = explain(report, case["question"], destination, manifest["model"], ollama_url,
                                 knowledge_url if mode == "retrieval" else None,
                                 case["knowledge_query"] if mode == "retrieval" else None, timeout=120)
                identity = result.get("model")
                if identity and identity["digest"] != manifest["model_digest"]:
                    raise ValueError("Model differs from frozen identity")
                verification = verify_explanation(report, destination)
                row = {"case": case["id"], "mode": mode, "verification": verification,
                       **score(case, result, read(destination / "model-context.json"))}
                rows.append(row)
                write(output / "partial.json", {"complete": False, "rows": rows})
                print(case["id"], mode, result["status"], flush=True)
    summary = {"complete": True, "manifest_sha256": expected_hash, "prompt_version": manifest["prompt_version"],
               "rows": rows, "semantic_quality": "unassessed", "human_review": "pending"}
    write(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("--spec", type=Path, required=True)
    frozen.add_argument("--output", type=Path, required=True)
    frozen.add_argument("--model", required=True)
    frozen.add_argument("--model-digest", required=True)
    runner = commands.add_parser("run")
    runner.add_argument("--manifest", type=Path, required=True)
    runner.add_argument("--manifest-sha256", required=True)
    runner.add_argument("--output", type=Path, required=True)
    runner.add_argument("--ollama-url", required=True)
    runner.add_argument("--knowledge-url")
    args = parser.parse_args()
    result = freeze(args.root, args.spec, args.output, args.model, args.model_digest) if args.command == "freeze" else assess(
        args.root, args.manifest, args.manifest_sha256, args.output, args.ollama_url, args.knowledge_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
