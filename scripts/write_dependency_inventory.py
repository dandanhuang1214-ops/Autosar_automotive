from __future__ import annotations

import argparse
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


TRACKED_DISTRIBUTIONS = (
    "automotive-workbench",
    "cantools",
    "python-can",
    "can-isotp",
    "udsoncan",
    "jsonschema",
    "mypy",
    "ruff",
)


def build_inventory() -> dict[str, object]:
    packages: list[dict[str, str]] = []
    for distribution in TRACKED_DISTRIBUTIONS:
        try:
            resolved = version(distribution)
        except PackageNotFoundError:
            resolved = "not-installed"
        packages.append({"name": distribution, "version": resolved})
    return {
        "artifact_type": "resolved-dependency-inventory",
        "schema_version": "resolved-dependency-inventory-0.1",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_inventory(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
