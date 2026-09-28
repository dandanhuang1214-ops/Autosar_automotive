"""P24 development evaluation; deterministic evidence queries, no held-out claim."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from automotive_workbench.arxml_bridge import import_bytes  # noqa: E402
from automotive_workbench.engineering_review import (  # noqa: E402
    canonical, catalog, digest, verify_engineering_review,
)
from automotive_workbench.review import _resolve_json_pointer  # noqa: E402


def run(output: Path, sources: Path | None = None) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ValueError("Evaluation output must be absent")
    output = output.resolve()
    output.mkdir(parents=True)
    owned_sources = sources is None
    sources = sources.resolve() if sources else output / "sources"
    if owned_sources:
        for script, name in [
            ("run_communication_graph_scenarios.py", "graph"),
            ("run_arxml_scenarios.py", "arxml"),
            ("run_external_project_scenarios.py", "project"),
        ]:
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script), "--output", str(sources / name)],
                capture_output=True, text=True, timeout=300, cwd=ROOT,
            )
            if process.returncode:
                raise ValueError(process.stdout + process.stderr)
    partial = sources / "arxml/partial.json"
    if not partial.exists():
        original = (ROOT / "examples/generate_arxml/xml/model.arxml").read_bytes()
        changed = original.replace(b"<PERIOD>", b'<PERIOD UNRECOGNIZED="synthetic-mutation">', 1)
        partial.write_text(json.dumps(import_bytes(changed, "synthetic-unsupported.arxml", {}), indent=2) + "\n", encoding="utf-8")
    fixture = ROOT / "tests/fixtures/engineering-review-development.json"
    raw = fixture.read_bytes()
    dataset = json.loads(raw)
    cases = dataset["cases"]
    ids = [c["question_id"] for c in cases]
    if len(ids) != 30 or len(set(ids)) != 30 or set(ids) != {q["id"] for q in catalog()["questions"]}:
        raise ValueError("Development set must cover 30 distinct frozen questions")
    observations = []
    failures = []
    for case in cases:
        q = case["question_id"]
        directory = output / "answers" / q
        process = subprocess.run(
            [sys.executable, "-m", "automotive_workbench.cli", "review-engineering", str(sources / case["source"]), "--question", q, "--output", str(directory)],
            capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
        expected_exit = 2 if case["expected_status"] == "refused" else 0
        if process.returncode != expected_exit:
            raise ValueError(f"{q}: {process.stdout} {process.stderr}")
        result = json.loads((directory / "engineering-review.json").read_text(encoding="utf-8"))
        passed = result["status"] == case["expected_status"]
        checks = []
        for gold in case["checks"]:
            value = _resolve_json_pointer(result, gold["pointer"])
            op = gold["operator"]
            if op == "equals":
                ok = canonical(value) == canonical(gold["value"])
            elif op == "contains":
                ok = gold["value"] in value
            elif op == "nonempty":
                ok = isinstance(value, (list, dict)) and bool(value)
            else:
                raise ValueError("Unknown gold operator")
            passed = passed and ok
            checks.append(dict(pointer=gold["pointer"], passed=ok))
        verification = verify_engineering_review(directory / "engineering-review.json")
        observations.append(dict(question_id=q, source_sha256=result["source"]["sha256"], status=result["status"], passed=passed, gold_checks=checks, citations=verification["citations"]))
        if not passed:
            failures.append(q)
    # Move the whole generated evidence tree; relative citations must survive removal
    # of the original location. Externally supplied local evidence stays untouched.
    migrated = 0
    if owned_sources:
        target = output.with_name(output.name + "-migrated")
        if target.exists():
            raise ValueError("Migration destination exists")
        shutil.move(str(output), target)
        try:
            for path in sorted((target / "answers").glob("*/engineering-review.json")):
                verify_engineering_review(path)
                migrated += 1
        finally:
            shutil.move(str(target), output)
    summary = {
        "status": "failed" if failures else "passed",
        "evaluation_version": "p24-development-0.1",
        "split": "development",
        "dataset_sha256": digest(raw),
        "catalog_sha256": digest(canonical(catalog()).encode()),
        "metrics": {
            "deterministic_questions": {"passed": len(cases) - len(failures), "total": len(cases)},
            "citation_replay": {"passed": len(observations), "total": len(cases)},
            "refusal": {"passed": sum(x["status"] == "refused" and x["passed"] for x in observations), "total": sum(c["expected_status"] == "refused" for c in cases)},
            "migration": {"passed": migrated, "total": len(cases) if owned_sources else 0},
            "semantic_retrieval": "not-run; fixed-json-pointer selection only",
            "model": "not-run",
            "independent_held_out": "pending; these cases participated in development",
        },
        "cases": observations,
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise ValueError("Development gold failed: " + ", ".join(failures))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", type=Path, help="Reuse existing local source scenarios; migration not measured")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.sources), ensure_ascii=False, indent=2))
