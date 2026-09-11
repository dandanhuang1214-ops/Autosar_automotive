from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automotive_workbench.communication_delivery import run_communication_delivery
from automotive_workbench.evidence_capsule import export_evidence_capsule
if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_distribution_support = importlib.import_module("scripts.check_installed_distribution")
_build_wheel = _distribution_support._build_wheel
_run = _distribution_support._run
_sha256_file = _distribution_support._sha256_file
_venv_paths = _distribution_support._venv_paths


def run_installed_capsule_consumer(
    project_root: Path,
    output: Path,
) -> dict[str, Any]:
    """Verify a relocated evidence capsule with an isolated installed wheel."""
    project_root = project_root.resolve()
    if not (project_root / "pyproject.toml").is_file():
        raise ValueError("Project root must contain pyproject.toml")
    if output.is_symlink():
        raise ValueError("Installed capsule consumer output must not be a symlink")
    output = output.resolve()
    if output.exists() and not output.is_dir():
        raise ValueError("Installed capsule consumer output must be a directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Installed capsule consumer output must be empty or absent")

    output.mkdir(parents=True, exist_ok=True)
    build_env = os.environ.copy()
    build_env.pop("PYTHONPATH", None)
    build_env.pop("PYTHONHOME", None)

    with tempfile.TemporaryDirectory() as temporary:
        isolation_root = Path(temporary).resolve()
        producer_root = isolation_root / "producer"
        delivery = producer_root / "delivery"
        capsule = producer_root / "capsule"
        relocated_capsule = isolation_root / "consumer-workdir" / "capsule"
        consumer_output = isolation_root / "consumer-output"
        wheel_dir = isolation_root / "wheel"
        wheel_dir.mkdir()

        dbc = project_root / "examples" / "window_control" / "window_control.dbc"
        intent = project_root / "examples" / "window_control" / "bsw_intent.json"
        run_communication_delivery(dbc, intent, delivery, base=project_root)
        capsule_report = export_evidence_capsule(
            delivery, capsule, base=project_root
        )
        relocated_capsule.parent.mkdir()
        shutil.copytree(capsule, relocated_capsule)

        _build_wheel(project_root, wheel_dir, build_env)
        wheels = sorted(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected exactly one wheel, found {len(wheels)}")
        wheel = wheels[0]
        wheel_sha256 = _sha256_file(wheel)

        environment_root = isolation_root / "consumer-env"
        _run(
            [sys.executable, "-m", "venv", str(environment_root)],
            cwd=relocated_capsule.parent,
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
            cwd=relocated_capsule.parent,
            env=build_env,
        )
        metadata = json.loads(
            _run(
                [
                    str(consumer_python),
                    "-I",
                    "-c",
                    (
                        "import json,automotive_workbench as a;"
                        "print(json.dumps({'module':a.__file__}))"
                    ),
                ],
                cwd=relocated_capsule.parent,
                env=build_env,
            )
        )
        if Path(metadata["module"]).resolve().is_relative_to(project_root):
            raise RuntimeError("Installed capsule consumer imported from checkout")

        cli_result = json.loads(
            _run(
                [
                    str(workbench),
                    "verify-evidence-capsule",
                    str(relocated_capsule),
                    "--output",
                    str(consumer_output),
                ],
                cwd=relocated_capsule.parent,
                env=build_env,
            )
        )
        persisted_path = consumer_output / "evidence-capsule-verification.json"
        persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
        if cli_result != persisted or persisted.get("status") != "passed":
            raise RuntimeError("Installed capsule verification did not pass consistently")
        expected_counts = (
            capsule_report["artifact_count"],
            capsule_report["dependency_count"],
        )
        verified_counts = (
            persisted["verified_artifact_count"],
            persisted["verified_dependency_count"],
        )
        if verified_counts != expected_counts:
            raise RuntimeError("Installed capsule verification counts are incomplete")

        result = {
            "artifact_type": "installed-capsule-consumer",
            "schema_version": "installed-capsule-consumer-0.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "passed",
            "runtime": {
                "implementation": platform.python_implementation(),
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            "wheel_sha256": wheel_sha256,
            "capsule_report_sha256": _sha256_file(
                relocated_capsule / "evidence-capsule-report.json"
            ),
            "verification_sha256": _sha256_file(persisted_path),
            "verified_file_count": persisted["verified_file_count"],
            "verified_artifact_count": persisted["verified_artifact_count"],
            "verified_dependency_count": persisted["verified_dependency_count"],
            "checks": [
                "capsule-produced",
                "capsule-relocated",
                "wheel-built",
                "isolated-install",
                "checkout-import-excluded",
                "installed-capsule-verification",
                "verification-counts-complete",
            ],
        }

    report_path = output / "installed-capsule-consumer.json"
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
    result = run_installed_capsule_consumer(args.project_root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
