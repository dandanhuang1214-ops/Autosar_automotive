"""Build the audited POSIX baseline and emit an executable-bound execution input."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from automotive_workbench.external_ecu import write_json, read_json  # noqa: E402
from automotive_workbench.can_io import sha256_file  # noqa: E402

COMMIT = "dbd6e118a9aaa2db36e4461ce76655e8f285598d"
SOURCES = {
    "can_source": "executables/referenceApp/platforms/posix/main/src/systems/CanSystem.cpp",
    "docan_source": "executables/referenceApp/application/src/systems/DoCanSystem.cpp",
    "uds_source": "executables/referenceApp/application/src/systems/UdsSystem.cpp",
}


def build(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Build output must be absent")

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(source), *args], text=True
        ).strip()

    if git("rev-parse", "HEAD") != COMMIT or git(
        "status", "--porcelain", "--untracked-files=all"
    ):
        raise ValueError("Build requires the fixed, clean OpenBSW checkout")
    output.mkdir(parents=True)
    commands = [
        ["cmake", "--preset", "posix-freertos"],
        [
            "cmake",
            "--build",
            "--preset",
            "posix-freertos",
            "--config",
            "Release",
            "--clean-first",
            "--parallel",
            "4",
        ],
    ]
    for command, name in zip(commands, ("configure", "build")):
        with (output / (name + ".log")).open("wb") as log:
            subprocess.run(
                command,
                cwd=source,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=600,
            )
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Source tree changed during build")
    files = {role: source / path for role, path in SOURCES.items()}
    files.update(
        executable=source
        / "build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf",
        cache=source / "build/posix-freertos/CMakeCache.txt",
        configure_log=output / "configure.log",
        build_log=output / "build.log",
    )
    profile = read_json(ROOT / "examples/openbsw/read_cf01.json")
    record = {
        "schema_version": "external-ecu-build-0.1",
        "source_commit": COMMIT,
        "preset": "posix-freertos",
        "configuration": "Release",
        "bindings": {
            "channel": "vcan0",
            **{
                key: profile[key]
                for key in ("request_id", "response_id", "did", "expected_data_hex")
            },
        },
        "commands": commands,
        "tools": {
            name: subprocess.check_output([tool, "--version"], text=True).splitlines()[
                0
            ]
            for name, tool in (
                ("cmake", "cmake"),
                ("compiler", "c++"),
                ("ninja", "ninja"),
            )
        },
        "files": [
            {"role": role, "path": str(path), "sha256": sha256_file(path)}
            for role, path in sorted(files.items())
        ],
    }
    write_json(output / "build.json", record)
    write_json(output / "profile.json", profile)
    write_json(
        output / "execution.json",
        {
            "schema_version": "external-ecu-execution-0.1",
            "build": "build.json",
            "profile": "profile.json",
            "channel": "vcan0",
            "startup_delay_s": 1.0,
            "shutdown_timeout_s": 1.0,
            "launch_ecu": True,
            "fault": "none",
        },
    )
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
