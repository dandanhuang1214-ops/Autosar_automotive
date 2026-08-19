from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    paths = [*Path("schemas").glob("*.json"), *Path("examples").rglob("*.json")]
    if not paths:
        raise SystemExit("No JSON contracts or examples found")
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"valid json: {path}")


if __name__ == "__main__":
    main()
