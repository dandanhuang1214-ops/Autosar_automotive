from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def check_blocked_evidence(output: Path, cli_outcome: str) -> dict[str, Any]:
    if cli_outcome != "failure":
        raise ValueError("Blocked communication-chain CLI outcome must be failure")
    combined_path = output / "communication-evidence-report.json"
    runtime_path = output / "runtime" / "can-runtime-report.json"
    if not combined_path.is_file() or not runtime_path.is_file():
        raise ValueError("Blocked communication-chain reports are missing")
    combined = json.loads(combined_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    reason = combined.get("reason")
    if reason not in {"interface_missing", "unsupported_platform"}:
        raise ValueError(f"Unexpected blocked reason: {reason!r}")
    if combined.get("status") != "blocked" or runtime.get("status") != "blocked":
        raise ValueError("Communication chain and runtime must both be blocked")
    if runtime.get("backend_probe", {}).get("status") != "blocked":
        raise ValueError("Backend probe must be blocked")
    if combined.get("finding_count") != 0:
        raise ValueError("Environmental blocking must not create mismatch findings")
    if {item.get("status") for item in combined.get("bindings", [])} != {"blocked"}:
        raise ValueError("All communication bindings must be blocked")
    filters = runtime.get("isolation", {}).get("frame_filters", [])
    if [item.get("can_id_hex") for item in filters] != ["0x100", "0x200"]:
        raise ValueError("Communication runtime must declare exact 0x100/0x200 filters")
    result = {
        "artifact_type": "communication-backend-blocked-exercise",
        "schema_version": "communication-backend-blocked-exercise-0.1",
        "status": "passed",
        "cli_outcome": cli_outcome,
        "blocked_reason": reason,
        "runtime_backend": runtime.get("backend"),
        "binding_count": len(combined["bindings"]),
    }
    (output / "communication-backend-blocked-exercise.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--cli-outcome", required=True)
    args = parser.parse_args()
    try:
        result = check_blocked_evidence(args.output, args.cli_outcome)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
