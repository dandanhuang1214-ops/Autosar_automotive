"""Run the public project delivery flow using only an isolated wheel installation."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
support = importlib.import_module("scripts.check_installed_distribution")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inventory(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): support._sha256_file(p)
            for p in sorted(root.rglob("*")) if p.is_file()}


def assert_isolated(metadata: dict[str, Any], checkout: Path, environment: Path) -> None:
    module = Path(metadata["module"]).resolve()
    if module.is_relative_to(checkout.resolve()) or not module.is_relative_to(environment.resolve()):
        raise RuntimeError("Consumer module must come from the isolated installed environment")
    if Path(metadata["prefix"]).resolve() != environment.resolve():
        raise RuntimeError("Consumer interpreter must use the isolated environment")


def prepare_examples(checkout: Path, target: Path) -> None:
    for name, folder, filename in [
        ("window", "window_control", "project-declared.json"),
        ("thermal", "thermal_control", "project.json"),
    ]:
        source = checkout / "examples" / folder
        project = json.loads((source / filename).read_text(encoding="utf-8"))
        dest = target / name
        dest.mkdir(parents=True)
        write_json(dest / "project.json", project)
        for relative in project["inputs"].values():
            path = source / relative
            if not path.resolve().is_relative_to(source.resolve()):
                raise ValueError("Public example input must remain inside its project")
            (dest / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest / relative)
    shutil.copytree(target / "thermal", target / "scale-failure")
    dbc = target / "scale-failure/thermal_control.dbc"
    original = dbc.read_text(encoding="utf-8")
    changed = original.replace("(0.1,-40)", "(0.2,-40)", 1)
    if changed == original:
        raise RuntimeError("Expected thermal scale mutation site is missing")
    dbc.write_text(changed, encoding="utf-8")


def run(checkout: Path, output: Path, wheelhouse: Path | None = None) -> dict[str, Any]:
    checkout = checkout.resolve()
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Delivery output must be empty or absent and not a symlink")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONUTF8="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    commands: list[dict[str, Any]] = []
    wheels = output / "wheelhouse"
    wheels.mkdir()
    support._build_wheel(checkout, wheels, env)
    wheel = next(wheels.glob("automotive_workbench-*.whl"))
    requirement = f"{wheel}[can]"
    if wheelhouse is None:
        support._run([sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                      "--dest", str(wheels), requirement], cwd=checkout, env=env)
    else:
        for dependency in wheelhouse.resolve().glob("*.whl"):
            if not dependency.name.startswith("automotive_workbench-"):
                shutil.copy2(dependency, wheels / dependency.name)
    with tempfile.TemporaryDirectory(prefix="workbench-delivery-") as temporary:
        root = Path(temporary).resolve()
        if root.is_relative_to(checkout):
            raise RuntimeError("Temporary consumer directory must be outside checkout")
        environment = root / "venv"
        cwd = root / "work"
        cwd.mkdir()
        evidence = cwd / "original"
        prepare_examples(checkout, evidence / "examples")
        inputs = inventory(evidence / "examples")

        def command(name: str, args: list[str], expected: int = 0) -> str:
            begin = time.monotonic()
            process = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                                     text=True, encoding="utf-8", timeout=300)
            log = {"name": name, "argv": args, "exit_code": process.returncode,
                   "expected_exit_code": expected, "seconds": round(time.monotonic() - begin, 3),
                   "stdout": process.stdout, "stderr": process.stderr}
            commands.append(log)
            write_json(output / "commands.json", commands)
            if process.returncode != expected:
                raise RuntimeError(f"{name}: expected exit {expected}, got {process.returncode}; see commands.json")
            return process.stdout

        command("create-environment", [sys.executable, "-m", "venv", str(environment)])
        python, workbench = support._venv_paths(environment)
        command("offline-install", [str(python), "-m", "pip", "install", "--no-index",
                                    "--find-links", str(wheels), requirement])
        command("dependency-check", [str(python), "-m", "pip", "check"])
        metadata = json.loads(command("installed-origin", [str(python), "-I", "-c",
            "import json,sys,platform,importlib.metadata as m,automotive_workbench as a;"
            "print(json.dumps({'module':a.__file__,'prefix':sys.prefix,'python':sys.version,"
            "'platform':platform.platform(),'dependencies':{d.metadata['Name']:d.version for d in m.distributions()}}))"]))
        assert_isolated(metadata, checkout, environment)

        def cli(name: str, args: list[str], expected: int = 0) -> dict[str, Any]:
            return json.loads(command(name, [str(workbench), *args], expected))

        def report(name: str) -> Path:
            return evidence / "projects" / name / "bundle/project-report.json"

        statuses = {}
        for name in ("window", "thermal", "scale-failure"):
            target = evidence / "projects" / name
            result = cli(name, ["run-project", str(evidence / "examples" / name / "project.json"),
                                "--output", str(target)], 2 if name == "scale-failure" else 0)
            expected_status = "failed" if name == "scale-failure" else "passed"
            if result["status"] != expected_status or result["integrity_status"] != "passed":
                raise RuntimeError(f"{name}: project status or integrity mismatch")
            payload = json.loads(report(name).read_text(encoding="utf-8"))
            if name == "scale-failure" and payload["stages"]["communication"]["status"] != "skipped":
                raise RuntimeError("Configuration failure must prevent communication execution")
            review = cli(f"review-{name}", ["run-project-review", str(report(name)), "--output",
                                             str(evidence / "reviews" / name)])
            if review["status"] != "answered" or review["citation_validation"]["status"] != "passed":
                raise RuntimeError("Project review must retain valid citations")
            statuses[name] = result["status"]
        impact = cli("configuration-impact", ["compare-communication-config",
            str(evidence / "examples/thermal/project.json"),
            str(evidence / "examples/scale-failure/project.json"),
            "--output", str(evidence / "impact")])
        if impact["vectors"] != ["thermal-status"] or "thermal-status" not in impact["requirements"] or "pump-status" in impact["requirements"]:
            raise RuntimeError("Scale change must identify the affected thermal vector and requirement")
        comparison = cli("project-regression", ["compare-projects", str(report("thermal")),
            str(report("scale-failure")), "--output", str(evidence / "comparison")], 2)
        if comparison["status"] != "regressed":
            raise RuntimeError("Configuration failure must be a project regression")
        cli("impact-review", ["review-engineering", str(evidence / "impact/report.json"),
            "--question", "impact-acceptance", "--output", str(evidence / "impact-review")])
        moved = cwd / "relocated"
        evidence.rename(moved)
        if evidence.exists():
            raise RuntimeError("Original evidence path must be absent during replay")
        evidence = moved
        for name in statuses:
            project = evidence / "projects" / name
            replay = cli(f"replay-{name}", ["verify-evidence", str(project / "bundle"),
                str(project / "manifest.json"), "--base", str(project),
                "--output", str(evidence / "replay" / name)])
            if replay["status"] != "passed":
                raise RuntimeError("Relocated project integrity failed")
            review_dir = evidence / "reviews" / name
            citations = json.loads(command(f"citations-{name}", [str(python), "-I", "-c",
                "import json,sys;from pathlib import Path;from automotive_workbench.review import validate_citations;"
                "p=Path(sys.argv[1]);r=validate_citations(p/'review-request.json',json.loads((p/'review-result.json').read_text(encoding='utf-8')));"
                "print(json.dumps(r));sys.exit(0 if r['status']=='passed' else 2)", str(review_dir)]))
            if citations["status"] != "passed":
                raise RuntimeError("Relocated review citations failed")
        for name, verb, relative in [
            ("impact-replay", "verify-communication-graph", "impact/report.json"),
            ("comparison-replay", "verify-project-comparison", "comparison/project-comparison.json"),
            ("answer-replay", "verify-engineering-review", "impact-review/engineering-review.json"),
        ]:
            result = cli(name, [verb, str(evidence / relative)])
            if result["status"] != "passed":
                raise RuntimeError(f"{name}: replay did not pass")
        shutil.copytree(evidence, output / "portable")
    result = {"version": "installed-project-delivery-0.1", "status": "passed",
              "scope": "public synthetic projects, virtual CAN; no physical ECU or external-user acceptance",
              "seconds": round(time.monotonic() - started, 3), "runtime": metadata,
              "wheelhouse": inventory(wheels), "inputs": inputs, "projects": statuses,
              "impact_vectors": impact["vectors"], "comparison": comparison["status"],
              "relocation": "passed with original paths absent",
              "portable_files": inventory(output / "portable")}
    write_json(output / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, help="Existing platform-compatible dependency wheels; avoids downloads")
    args = parser.parse_args()
    print(json.dumps(run(args.project_root, args.output, args.wheelhouse), indent=2))
