"""Offline isolated-wheel acceptance of the complete P26 review/impact workflow."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_installed_distribution import (  # noqa: E402
    _build_wheel,
    _run,
    _sha256_file,
    _venv_paths,
)
from run_ecuc_engineering_scenarios import run  # noqa: E402
from run_ecuc_acceptance_scenarios import run as run_projects  # noqa: E402


def check(output: Path, project_acceptance: bool = False) -> dict[str, Any]:
    if output.is_symlink() or output.exists():
        raise ValueError("Installed ECUC output must be absent")
    output = output.resolve()
    wheel_dir = output / "wheel"
    wheel_dir.mkdir(parents=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    _build_wheel(ROOT, wheel_dir, env)
    wheels = list(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one wheel")
    wheel = wheels[0]
    with tempfile.TemporaryDirectory() as temporary:
        isolated = Path(temporary).resolve()
        environment = isolated / "venv"
        _run([sys.executable, "-m", "venv", str(environment)], cwd=isolated, env=env)
        python, _ = _venv_paths(environment)
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            cwd=isolated,
            env=env,
        )
        metadata = json.loads(
            _run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import json,sys,automotive_workbench as a;print(json.dumps({'module':a.__file__,'prefix':sys.prefix}))",
                ],
                cwd=isolated,
                env=env,
            )
        )
        module = Path(metadata["module"]).resolve()
        if (
            module.is_relative_to(ROOT)
            or not module.is_relative_to(environment)
            or Path(metadata["prefix"]).resolve() != environment
        ):
            raise ValueError("Installed ECUC consumer is not isolated")
        _run([str(python), "-m", "pip", "check"], cwd=isolated, env=env)
        result = (run_projects if project_acceptance else run)(
            isolated / "flow", python
        )
        shutil.copytree(isolated / "flow", output / "evidence")
        # Verify copied final evidence from outside the repository with the installed interpreter.
        replay = json.loads(
            _run(
                [
                    str(python),
                    "-m",
                    "automotive_workbench.cli",
                    "verify-ecuc-project"
                    if project_acceptance
                    else "verify-ecuc-impact",
                    str(
                        output
                        / (
                            "evidence/delivery/projects/integration/bundle/project-report.json"
                            if project_acceptance
                            else "evidence/portable/comparisons/signal/ecuc-impact.json"
                        )
                    ),
                ],
                cwd=isolated,
                env=env,
            )
        )
        if replay["status"] != "passed":
            raise ValueError("Installed final relocation replay failed")
    summary = {
        "status": "passed",
        "wheel": wheel.name,
        "wheel_sha256": _sha256_file(wheel),
        "consumer_metadata": metadata,
        "workflow": result,
        "copied_replay": replay,
        "checks": [
            "offline-no-deps-install",
            "checkout-import-excluded",
            "pip-check",
            "complete-engineering-flow",
            "copied-evidence-replay",
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-acceptance", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.output, args.project_acceptance), indent=2))
