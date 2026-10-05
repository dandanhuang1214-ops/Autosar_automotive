"""Verify P30 fact gate with a dependency-free isolated installed wheel."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from check_installed_distribution import _build_wheel, _run, _sha256_file, _venv_paths
from run_project_explanation_scenarios import run
from run_model_explanation_scenarios import run as run_model

ROOT = Path(__file__).resolve().parents[1]


def check(output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Installed explanation output must be absent")
    output = output.resolve()
    wheel_dir = output / "wheel"
    wheel_dir.mkdir(parents=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    _build_wheel(ROOT, wheel_dir, env)
    wheels = list(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected one wheel")
    wheel = wheels[0]
    with tempfile.TemporaryDirectory() as temporary:
        isolated = Path(temporary).resolve()
        environment = isolated / "venv"
        _run([sys.executable, "-m", "venv", str(environment)], cwd=isolated, env=env)
        python, _ = _venv_paths(environment)
        _run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], cwd=isolated, env=env)
        module = Path(_run([str(python), "-I", "-c", "import automotive_workbench as a; print(a.__file__)"], cwd=isolated, env=env).strip()).resolve()
        if module.is_relative_to(ROOT) or not module.is_relative_to(environment):
            raise ValueError("Installed consumer imported checkout")
        result = run(isolated / "flow", python)
        model_result = run_model(isolated / "model-flow", python)
        shutil.copytree(isolated / "model-flow", output / "model-evidence")
        shutil.copytree(isolated / "flow", output / "evidence")
        model_replay = json.loads(_run([str(python), "-m", "automotive_workbench.cli", "verify-model-explanation",
                                        str(output / "model-evidence/project/bundle/project-report.json"),
                                        str(output / "model-evidence/normal")], cwd=isolated, env=env))
        if model_replay["status"] != "passed":
            raise ValueError("Installed model archive replay failed")
        replays = []
        for name in ("integration", "transmitter"):
            evidence = output / "evidence"
            replay = json.loads(_run([str(python), "-m", "automotive_workbench.cli", "validate-project-explanation",
                                     str(evidence / f"搬移 {name}/project-report.json"),
                                     str(evidence / f"{name}-request.json"), str(evidence / f"{name}-answer.json")], cwd=isolated, env=env))
            if replay["status"] != "passed":
                raise ValueError("Archived explanation replay failed")
            replays.append(replay)
    summary = {"status": "passed", "wheel_sha256": _sha256_file(wheel), "workflow": result,
               "model_workflow": model_result, "model_replay": model_replay, "archived_replays": replays, "installation": "offline-no-deps-checkout-excluded"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output), indent=2))
