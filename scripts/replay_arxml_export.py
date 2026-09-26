"""Generate public SWC XML from the same pinned producer/input as P16."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = "e912e404d52e671c7561d518d9989af3382fce51"


def replay(repository: Path, python: Path, output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Producer output must be empty or absent")
    archive = subprocess.run(
        ["git", "-C", str(repository), "archive", "--format=zip", REVISION],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    python = python.absolute()
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
        timeout=30,
    )
    with tempfile.TemporaryDirectory(prefix="p22-producer-") as directory:
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
                    raise ValueError("Unsafe producer archive member")
            zipped.extractall(producer)
        output.mkdir(parents=True, exist_ok=True)
        output = output.resolve()
        shutil.copyfile(
            ROOT / "examples/generate_arxml/bridge/baseline/source.docx",
            output / "source.docx",
        )
        script = producer / "scripts/docx_to_contract.py"
        arguments = [
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
            "--arxml",
            "model.arxml",
        ]
        completed = subprocess.run(
            [str(python), str(script), *arguments],
            cwd=output,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        (output / "producer.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output / "producer.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise ValueError(f"Producer exit {completed.returncode}; inspect {output}")

        def sha(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        result = dict(
            tool="Generate-Arxml",
            tool_version="0.1.0",
            revision=REVISION,
            repository="https://github.com/dandanhuang1214-ops/Generate-Arxml",
            provenance_kind="local-execution-record-not-producer-authentication",
            producer_archive_sha256=hashlib.sha256(archive).hexdigest(),
            producer_script_sha256=sha(script),
            source_docx_sha256=sha(output / "source.docx"),
            arxml_sha256=sha(output / "model.arxml"),
            arguments=arguments,
            exit_code=completed.returncode,
            runtime=json.loads(inventory.stdout),
        )
        (output / "provenance.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--producer-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(replay(args.repository, args.producer_python, args.output), indent=2)
    )


if __name__ == "__main__":
    main()
