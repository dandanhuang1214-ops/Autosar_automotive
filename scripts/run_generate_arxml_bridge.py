"""Replay a pinned Generate-Arxml DOCX export and its Workbench acceptance cases."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

PINNED_REVISION = "e912e404d52e671c7561d518d9989af3382fce51"


def replay(
    repository: Path, python: Path, output: Path, revision: str = PINNED_REVISION
) -> dict:
    from create_public_delivery_docx import create_document
    from automotive_workbench.can_io import BusConfig, sha256_file
    from automotive_workbench.project_workflow import run_project

    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Producer revision must be a full commit hash")
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Bridge output must be empty or absent")
    repository, python, output = (
        repository.resolve(),
        python.absolute(),
        output.resolve(),
    )
    archive = subprocess.run(
        ["git", "-C", str(repository), "archive", "--format=zip", revision],
        check=True,
        capture_output=True,
    ).stdout
    output.mkdir(parents=True, exist_ok=True)
    results = []
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    inventory = subprocess.run(
        [
            str(python),
            "-c",
            'import json,sys,importlib.metadata as m; print(json.dumps({"python":sys.version,"dependencies":{n:m.version(n) for n in ["openpyxl","lxml","pydantic","pyyaml","python-docx"]}}))',
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    with tempfile.TemporaryDirectory(prefix="workbench-arxml-") as directory:
        producer = Path(directory)
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            for member in zipped.infolist():
                path = PurePosixPath(member.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.filename
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ValueError("Unsafe producer archive entry")
            zipped.extractall(producer)
        script = producer / "scripts/docx_to_contract.py"
        script_hash = sha256_file(script)
        for name, resolution, omit_init, expected_exit, expected_status in [
            ("baseline", "1", False, 0, "passed"),
            ("scale-change", "2", False, 0, "failed"),
            ("missing-init", "1", True, 1, "failed"),
        ]:
            case = output / name
            create_document(
                case / "source.docx", resolution=resolution, omit_init=omit_init
            )
            command = [
                str(python),
                str(script),
                "--input",
                "source.docx",
                "--contract",
                "contract.json",
                "--excel",
                "model.xlsx",
                "--report-json",
                "issues.json",
                "--mode",
                "signal",
                "--profile",
                "signal_atomic_davinci",
            ]
            completed = subprocess.run(
                command, cwd=case, env=env, capture_output=True, text=True, timeout=60
            )
            (case / "producer.stdout.txt").write_text(
                completed.stdout, encoding="utf-8"
            )
            (case / "producer.stderr.txt").write_text(
                completed.stderr, encoding="utf-8"
            )
            if completed.returncode != expected_exit:
                raise ValueError(
                    f"{name}: unexpected producer exit {completed.returncode}; see {case}"
                )
            project = json.loads(
                (
                    ROOT / "examples/generate_arxml/bridge" / name / "project.json"
                ).read_text(encoding="utf-8")
            )
            project["generation"].update(
                revision=revision,
                exit_code=completed.returncode,
                sha256={
                    key: sha256_file(case / file)
                    for key, file in [
                        ("contract", "contract.json"),
                        ("issue_report", "issues.json"),
                        ("source_docx", "source.docx"),
                    ]
                },
            )
            for source, destination in [
                ("window_control.dbc", "dbc.dbc"),
                ("bsw_intent.json", "intent.json"),
            ]:
                shutil.copyfile(
                    ROOT / "examples/window_control" / source, case / destination
                )
            (case / "project.json").write_text(
                json.dumps(project, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            accepted = run_project(
                case / "project.json",
                case / "acceptance",
                BusConfig("virtual", "arxml-bridge-" + name),
            )
            report = json.loads(
                Path(accepted["report_json"]).read_text(encoding="utf-8")
            )
            if (
                accepted["status"] != expected_status
                or accepted["integrity_status"] != "passed"
            ):
                raise ValueError(
                    f"{name}: acceptance differed from expected {expected_status}"
                )
            if (
                name != "baseline"
                and report["stages"]["communication"]["status"] != "skipped"
            ):
                raise ValueError(
                    f"{name}: rejected configuration reached communication runtime"
                )
            results.append(
                {
                    "case": name,
                    "producer_exit_code": completed.returncode,
                    "project_status": accepted["status"],
                    "generation_status": report["stages"]["generation"]["status"],
                    "canonical_status": report["stages"]["canonical"]["status"],
                    "communication_status": report["stages"]["communication"]["status"],
                    "source_hashes": project["generation"]["sha256"],
                    "project_report_sha256": sha256_file(Path(accepted["report_json"])),
                }
            )
    result = {
        "artifact_type": "generate-arxml-bridge-replay",
        "status": "passed",
        "producer_revision": revision,
        "producer_archive_sha256": hashlib.sha256(archive).hexdigest(),
        "producer_script_sha256": script_hash,
        "producer_runtime": json.loads(inventory.stdout),
        "cases": results,
    }
    (output / "bridge-replay.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--producer-python", type=Path, required=True)
    parser.add_argument("--revision", default=PINNED_REVISION)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            replay(args.repository, args.producer_python, args.output, args.revision),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
