"""Separate P24 retrieval, rules, citations, severity, and sealed-negative metrics."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from automotive_workbench.engineering_review import (  # noqa: E402
    canonical, catalog, digest, verify_engineering_review,
)
from automotive_workbench.engineering_search import search_questions  # noqa: E402
from automotive_workbench.project_comparison import validate_project_comparison  # noqa: E402
from automotive_workbench.review import _resolve_json_pointer, validate_citations  # noqa: E402


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cli(args: list[str]) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(
        [sys.executable, "-m", "automotive_workbench.cli", *args],
        capture_output=True, timeout=120, cwd=ROOT,
    )
    # CLI uses UTF-8 when supported and ASCII JSON escapes otherwise. Both decode here.
    try:
        result = json.loads(process.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("CLI did not emit JSON: " + process.stderr.decode("utf-8", errors="replace")) from exc
    return process.returncode, result


def assertions(value: dict[str, Any], gold: list[dict[str, Any]]) -> bool:
    if not gold:
        raise ValueError("Assessment case requires assertions")
    for rule in gold:
        try:
            actual = _resolve_json_pointer(value, rule["pointer"])
            operator = rule["operator"]
            if operator == "project":
                actual = [[item[field] for field in rule["fields"]] for item in actual]
            elif operator == "contains":
                if rule["value"] not in actual:
                    return False
                continue
            elif operator != "equals":
                raise ValueError("Unsupported assessment operator: " + operator)
            if canonical(actual) != canonical(rule["value"]):
                return False
        except (KeyError, IndexError, TypeError):
            return False
    return True


def measure(passed: int, total: int) -> dict[str, Any]:
    return {"passed": passed, "total": total, "rate": passed / total if total else None}


def retrieval(cases: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for case in cases:
        result = search_questions(case["query"], 3, case.get("input_version"))
        ids = [c["question_id"] for c in result["candidates"]]
        target = case["expected_first"]
        rows.append({"query": case["query"], "expected_first": target, "ranked": ids,
                     "top1": (ids[0] == target if ids else target is None),
                     "hit_at3": (target in ids if target else not ids)})
    positives = [r for r in rows if r["expected_first"] is not None]
    negatives = [r for r in rows if r["expected_first"] is None]
    return {
        "catalog_top1": measure(sum(r["top1"] for r in positives), len(positives)),
        "catalog_hit_at3": measure(sum(r["hit_at3"] for r in positives), len(positives)),
        "catalog_no_match": measure(sum(r["top1"] for r in negatives), len(negatives)),
        "scope": "lexical catalog navigation; not semantic evidence retrieval or claim support",
    }, rows


def conditions(development: Path, output: Path) -> list[dict[str, Any]]:
    """Real CLI executions with unavailable synthetic builds, never a responder."""
    source = output / "condition-inputs"
    shutil.copytree(development / "sources/project/baseline/bundle/inputs", source)
    project = read(source / "project.json")
    project["inputs"] = {
        "dbc": "dbc.dbc", "contract": "contract.json", "intent": "intent.json",
        "vectors": "vectors.json", "arxml": "arxml.arxml",
        "provenance": "provenance.json", "execution": "runner-execution.json",
    }
    write(source / "project.json", project)
    build = read(source / "runner-build.json")
    for item in build["files"]:
        item["path"] = "absent.elf" if item["role"] == "executable" else "external-" + item["role"] + ".txt"
    original_profile = read(source / "runner-profile.json")
    rows = []
    for name in ("baseline", "build-change", "timeout-change"):
        candidate = copy.deepcopy(build)
        profile = dict(original_profile)
        if name == "build-change":
            candidate["source_commit"] = "1" * 40
        if name == "timeout-change":
            profile["timeout_s"] = original_profile["timeout_s"] + 1.0
        write(source / "runner-build.json", candidate)
        write(source / "runner-profile.json", profile)
        code, result = cli(["run-project", str(source / "project.json"), "--interface", "socketcan", "--channel", build["bindings"]["channel"], "--output", str(output / name)])
        if code != 3 or result["status"] != "blocked":
            raise ValueError("Condition fixture must stay offline blocked: " + name)
        if name == "baseline":
            continue
        code, compared = cli([
            "compare-projects", str(output / "baseline/bundle/project-report.json"),
            str(output / name / "bundle/project-report.json"), "--output", str(output / (name + "-compare")),
        ])
        verified = validate_project_comparison(output / (name + "-compare/project-comparison.json"))
        ok = code == 2 and compared["status"] == "not-comparable" and "project comparison basis differs" in compared["basis"]["reasons"] and verified["status"] == "passed"
        rows.append({"case": name, "passed": ok, "status": compared["status"], "reasons": compared["basis"]["reasons"]})
    return rows


def safe_child(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Fixture path escapes its generated directory")
    return path


def mutate(root: Path, report: Path, operations: list[dict[str, Any]]) -> None:
    """Data-only mutations on copies owned by this evaluator."""
    for operation in operations:
        path = report if operation["file"] == "$report" else safe_child(root, operation["file"])
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Mutation target must be an existing generated file")
        op = operation["op"]
        if op == "delete_file":
            path.unlink()
            continue
        if op == "text_replace":
            text = path.read_text(encoding="utf-8")
            if text.count(operation["old"]) != operation["count"]:
                raise ValueError("Fixture replacement anchor count differs")
            path.write_text(text.replace(operation["old"], operation["new"]), encoding="utf-8")
            continue
        value = read(path)
        pointer = operation["pointer"]
        parent, _, raw_key = pointer.rpartition("/")
        if not pointer.startswith("/"):
            raise ValueError("Mutation requires a non-root JSON Pointer")
        target = _resolve_json_pointer(value, parent)
        key: Any = int(raw_key) if isinstance(target, list) else raw_key.replace("~1", "/").replace("~0", "~")
        if op == "remove":
            del target[key]
        elif op == "set":
            target[key] = operation["value"]
        elif op == "file_hash":
            target[key] = digest(safe_child(root, operation["hash_file"]).read_bytes())
        else:
            raise ValueError("Unknown fixture mutation")
        write(path, value)


def verify_seal(manifest: dict[str, Any]) -> None:
    """All runtime sources are frozen, not just the top-level question module."""
    seal = manifest["freeze"]
    actual = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py"))
    if actual != sorted(p for p in seal["files"] if p.startswith("src/")):
        raise ValueError("Frozen runtime source inventory differs")
    for name, expected in seal["files"].items():
        if digest(safe_child(ROOT, name).read_bytes()) != expected:
            raise ValueError("Frozen implementation changed: " + name)
    if digest(canonical(catalog()).encode()) != seal["catalog_sha256"]:
        raise ValueError("Frozen question catalog changed")


def cohort_context(manifest: dict[str, Any], historical: bool = False) -> dict[str, Any]:
    if not historical:
        verify_seal(manifest)
    return {"split": "historical-regression" if historical else "held-out-after-freeze",
            "freeze_verified": not historical,
            "original_freeze": manifest["freeze"],
            "current_runtime_sha256": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                                       for p in sorted((ROOT / "src").rglob("*.py"))}}


def held_out(development: Path, output: Path, path: Path, historical: bool = False) -> dict[str, Any]:
    manifest = read(path)
    if manifest["split"] != "held-out-after-freeze":
        raise ValueError("Held-out split is required")
    context = cohort_context(manifest, historical)
    rows = []
    if len({c["id"] for c in manifest["cases"]}) != len(manifest["cases"]) or not manifest["cases"]:
        raise ValueError("Held-out case IDs must be unique and non-empty")
    if len(manifest["cases"]) < 6 or {c["classification"] for c in manifest["cases"]} != {"integrity-rejection", "scope-refusal"}:
        raise ValueError("Held-out requires both negative classes and at least six cases")
    if not manifest["retrieval"] or not any(c["expected_first"] is None for c in manifest["retrieval"]):
        raise ValueError("Held-out requires catalog no-match queries")
    for case in manifest["cases"]:
        directory = safe_child(output, case["id"])
        original = safe_child(development, case["source"])
        # Preserve the bundle basename required by portable project inventory rules.
        copied = directory / original.parent.name
        shutil.copytree(original.parent, copied)
        report = copied / original.name
        initial_hash = digest(report.read_bytes())
        if case["action"] == "review":
            mutate(copied, report, case["mutations"])
            code, result = cli(["review-engineering", str(report), "--question", case["question_id"], "--output", str(directory / "answer")])
            no_output = not (directory / "answer").exists()
        elif case["action"] == "verify":
            code, _ = cli(["review-engineering", str(report), "--question", case["question_id"], "--output", str(directory / "answer")])
            if code not in (0, 2):
                raise ValueError("Held-out verifier fixture could not produce its initial answer")
            answer_path = directory / "answer/engineering-review.json"
            mutate(directory / "answer", answer_path, case["mutations"])
            code, result = cli(["verify-engineering-review", str(answer_path)])
            no_output = True  # verifier has no output directory side effects
        else:
            raise ValueError("Unknown held-out action")
        ok = code == case["expected_exit"] and result["status"] == case["expected_status"]
        if case["expected_exit"] == 1:
            ok = ok and no_output and case["error_contains"] in result.get("message", "")
        if case["expected_status"] == "refused":
            ok = ok and verify_engineering_review(directory / "answer/engineering-review.json")["status"] == "passed"
        if case.get("checks"):
            ok = ok and assertions(result, case["checks"])
        write(directory / "observed.json", {"exit_code": code, "result": result})
        rows.append({"id": case["id"], "passed": ok, "source_before_sha256": initial_hash,
                     "exit_code": code, "status": result["status"], "classification": case["classification"]})
    metrics, searches = retrieval(manifest["retrieval"])
    for name in ("integrity-rejection", "scope-refusal"):
        selected = [r for r in rows if r["classification"] == name]
        metrics[name] = measure(sum(r["passed"] for r in selected), len(selected))
    moved = output.with_name(output.name + "-moved")
    if moved.exists():
        raise ValueError("Held-out migration destination exists")
    output.rename(moved)
    migration_passed = 0
    try:
        for case in manifest["cases"]:
            directory = moved / case["id"]
            if case["expected_status"] == "refused":
                checked = verify_engineering_review(directory / "answer/engineering-review.json")
                migration_passed += checked["status"] == "passed"
            elif case["action"] == "verify":
                code, value = cli(["verify-engineering-review", str(directory / "answer/engineering-review.json")])
                migration_passed += code == 1 and value["status"] == "error"
            else:
                original = Path(case["source"])
                code, value = cli(["review-engineering", str(directory / original.parent.name / original.name), "--question", case["question_id"], "--output", str(directory / "replay-answer")])
                migration_passed += code == 1 and value["status"] == "error" and not (directory / "replay-answer").exists()
    finally:
        moved.rename(output)
    metrics["migration"] = measure(migration_passed, len(manifest["cases"]))
    provenance = context if historical else {"freeze": manifest["freeze"]}
    return {"manifest_sha256": digest(path.read_bytes()), **provenance,
            "formation": manifest["formation"], "metrics": metrics, "cases": rows, "retrieval_cases": searches}


def run(development: Path, output: Path, heldout_path: Path | None = None, historical_path: Path | None = None) -> dict[str, Any]:
    if heldout_path and historical_path:
        raise ValueError("Choose either frozen held-out or historical regression")
    if output.exists() or output.is_symlink():
        raise ValueError("Assessment output must be absent")
    development, output = development.resolve(), output.resolve()
    fixture = ROOT / "tests/fixtures/engineering-review-assessment-development.json"
    gold = read(fixture)
    if gold["catalog_sha256"] != digest(canonical(catalog()).encode()):
        raise ValueError("Development assessment catalog differs")
    if {c["question_id"] for c in gold["cases"]} != {q["id"] for q in catalog()["questions"]} or len(gold["cases"]) != 30:
        raise ValueError("Assessment must cover the frozen 30 distinct questions")
    output.mkdir(parents=True)
    rows = []
    for case in gold["cases"]:
        path = development / "answers" / case["question_id"] / "engineering-review.json"
        value = read(path)
        verified = verify_engineering_review(path)
        rows.append({"question_id": case["question_id"], "passed": value["status"] == case["expected_status"] and assertions(value, case["checks"]),
                     "citations_valid": verified["status"] == "passed", "source_sha256": value["source"]["sha256"]})
    search_metrics, search_rows = retrieval(gold["retrieval"])
    source = development / "sources/project/static-failure/bundle/project-report.json"
    code, reviewed = cli(["run-project-review", str(source), "--output", str(output / "severity")])
    request = output / "severity/review-request.json"
    severity_citations = [c for c in reviewed["citations"] if c["locator"].get("pointer", "").endswith("/severity")]
    severity_ok = code == 0 and canonical(reviewed["findings"]) == canonical(gold["severity_expected"]) and [c["content"] for c in severity_citations] == ["ERROR"] and validate_citations(request, reviewed)["status"] == "passed"
    tamper = []
    for name in ("downgraded", "omitted", "invented"):
        changed = copy.deepcopy(reviewed)
        if name == "downgraded":
            changed["findings"][0]["severity"] = "WARNING"
        elif name == "omitted":
            changed["findings"] = []
        else:
            changed["findings"].append({**changed["findings"][0], "code": "INVENTED"})
        verification = validate_citations(request, changed)
        tamper.append({"case": name, "passed": verification["status"] == "failed"})
        write(output / ("severity-" + name + ".json"), {"mutated_result": changed, "verification": verification})
    absent = read(development / "answers/arxml-references/engineering-review.json")
    no_invention = all("severity" not in f for f in absent["facts"][1]["value"])
    comparison_rows = conditions(development, output)
    metrics = {
        **search_metrics,
        "deterministic_gold": measure(sum(r["passed"] for r in rows), len(rows)),
        "citation_replay": measure(sum(r["citations_valid"] for r in rows), len(rows)),
        "severity_fidelity": measure(int(severity_ok) + int(no_invention), 2),
        "finding_tamper_rejection": measure(sum(r["passed"] for r in tamper), len(tamper)),
        "condition_comparison": measure(sum(r["passed"] for r in comparison_rows), len(comparison_rows)),
        "model": {"status": "not-run", "reason": "No model needed to resolve these fixed evidence facts; causal explanation remains unverified."},
    }
    cohort_path = historical_path or heldout_path
    independent = held_out(development, output / ("historical-regression" if historical_path else "held-out"), cohort_path, historical=historical_path is not None) if cohort_path else None
    all_metrics = [*metrics.values(), *(independent["metrics"].values() if independent else [])]
    passed = all(m["passed"] == m["total"] for m in all_metrics if isinstance(m, dict) and "total" in m)
    result = {"evaluation_version": "p24-assessment-0.2" if historical_path else "p24-assessment-0.1", "status": "passed" if passed else "failed",
              "development_dataset_sha256": digest(fixture.read_bytes()), "metrics": metrics,
              "cases": rows, "retrieval_cases": search_rows, "finding_tamper_cases": tamper,
              "condition_cases": comparison_rows, "held_out": None if historical_path else independent}
    if historical_path:
        result["historical_regression"] = independent
    write(output / "summary.json", result)
    if not passed:
        raise ValueError("P24 assessment failed; inspect saved summary")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    cohort = parser.add_mutually_exclusive_group()
    cohort.add_argument("--held-out", type=Path)
    cohort.add_argument("--historical-regression", type=Path, help="Replay known historical negatives without claiming freeze or independence")
    args = parser.parse_args()
    result = run(args.development, args.output, args.held_out, args.historical_regression)
    print(json.dumps({"status": result["status"], "metrics": result["metrics"]}, indent=2))
