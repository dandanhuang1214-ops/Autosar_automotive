from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"Command failed with exit code {exc.returncode}: {detail}"
        ) from exc
    return completed.stdout


def _venv_paths(root: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return root / "Scripts" / "python.exe", root / "Scripts" / "workbench.exe"
    return root / "bin" / "python", root / "bin" / "workbench"


def _build_wheel(
    project_root: Path, wheel_dir: Path, build_env: dict[str, str]
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged_project = Path(temporary) / "project"
        (staged_project / "src").mkdir(parents=True)
        shutil.copy2(project_root / "pyproject.toml", staged_project / "pyproject.toml")
        shutil.copytree(
            project_root / "src" / "automotive_workbench",
            staged_project / "src" / "automotive_workbench",
        )
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_dir),
                str(staged_project),
            ],
            cwd=staged_project,
            env=build_env,
        )


def run_installed_distribution_smoke(
    project_root: Path,
    output: Path,
) -> dict[str, Any]:
    """Build and exercise the wheel without importing from the source checkout."""
    project_root = project_root.resolve()
    output = output.resolve()
    if not (project_root / "pyproject.toml").is_file():
        raise ValueError("Project root must contain pyproject.toml")
    project = tomllib.loads(
        (project_root / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    if output.is_symlink():
        raise ValueError("Distribution smoke output must not be a symlink")
    if output.exists() and not output.is_dir():
        raise ValueError("Distribution smoke output must be a directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Distribution smoke output must be empty or absent")

    wheel_dir = output / "wheel"
    wheel_dir.mkdir(parents=True)
    build_env = os.environ.copy()
    build_env.pop("PYTHONPATH", None)
    build_env.pop("PYTHONHOME", None)
    _build_wheel(project_root, wheel_dir, build_env)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected exactly one wheel, found {len(wheels)}")
    wheel = wheels[0]

    with tempfile.TemporaryDirectory() as temporary:
        isolation_root = Path(temporary).resolve()
        environment_root = isolation_root / "consumer-env"
        consumer_cwd = isolation_root / "consumer-workdir"
        consumer_cwd.mkdir()
        _run(
            [sys.executable, "-m", "venv", str(environment_root)],
            cwd=consumer_cwd,
            env=build_env,
        )
        consumer_python, workbench = _venv_paths(environment_root)
        _run(
            [
                str(consumer_python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            cwd=consumer_cwd,
            env=build_env,
        )
        metadata = json.loads(
            _run(
                [
                    str(consumer_python),
                    "-I",
                    "-c",
                    (
                        "import importlib.metadata as m,json,automotive_workbench as a;"
                        "print(json.dumps({'name':m.metadata('automotive-workbench')['Name'],"
                        "'version':m.version('automotive-workbench'),'module':a.__file__}))"
                    ),
                ],
                cwd=consumer_cwd,
                env=build_env,
            )
        )
        if (
            metadata["name"] != project["name"]
            or metadata["version"] != project["version"]
        ):
            raise RuntimeError("Installed distribution metadata differs from pyproject.toml")
        module_path = Path(metadata["module"]).resolve()
        if module_path.is_relative_to(project_root):
            raise RuntimeError("Installed smoke imported automotive_workbench from checkout")
        help_text = _run(
            [str(workbench), "--help"], cwd=consumer_cwd, env=build_env
        )
        if "trace" not in help_text or "verify-evidence-capsule" not in help_text:
            raise RuntimeError("Installed workbench entry point is missing expected commands")
        intent = project_root / "examples" / "window_control" / "bsw_intent.json"
        trace = json.loads(
            _run(
                [str(workbench), "trace", str(intent), "WindowPosition"],
                cwd=consumer_cwd,
                env=build_env,
            )
        )
        if trace.get("query") != "WindowPosition" or len(trace.get("nodes", [])) != 8:
            raise RuntimeError("Installed workbench trace result is incomplete")

    distribution = {
        "name": metadata["name"],
        "version": metadata["version"],
        "wheel": wheel.name,
        "wheel_sha256": _sha256_file(wheel),
        "wheel_size": wheel.stat().st_size,
    }
    shutil.rmtree(wheel_dir)
    result = {
        "artifact_type": "installed-distribution-smoke",
        "schema_version": "installed-distribution-smoke-0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "distribution": distribution,
        "runtime": {
            "implementation": platform.python_implementation(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "checks": [
            "wheel-built",
            "isolated-install",
            "distribution-metadata",
            "checkout-import-excluded",
            "console-entrypoint",
            "core-trace",
        ],
    }
    report_path = output / "installed-distribution-smoke.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_installed_distribution_smoke(args.project_root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
