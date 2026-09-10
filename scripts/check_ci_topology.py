from __future__ import annotations

import argparse
import re
from pathlib import Path


EXPECTED_JOBS = {
    "core-contracts",
    "runtime-evidence",
    "controlled-rejections",
    "runtime-currency",
}

STEP_OWNERS = {
    "Run core tests": "core-contracts",
    "Smoke-test installed wheel distribution": "core-contracts",
    "Validate checked-in JSON": "core-contracts",
    "Run minimum-error Ruff gate": {"core-contracts", "runtime-currency"},
    "Run virtual CAN runtime lab": "runtime-evidence",
    "Run complete communication evidence chain": "runtime-evidence",
    "Run fixed-report engineering review cohort": "runtime-evidence",
    "Run controlled evidence tamper rejection": "controlled-rejections",
    "Run controlled capsule tamper rejection": "controlled-rejections",
    "Exercise unavailable SocketCAN communication backend": "controlled-rejections",
    "Run controlled review rejection": "controlled-rejections",
    "Run Python 3.14 full regression": "runtime-currency",
}


def _job_sections(text: str) -> dict[str, str]:
    jobs_text = text.split("jobs:\n", 1)[1]
    matches = list(re.finditer(r"(?m)^  ([a-z][a-z0-9-]*):\s*$", jobs_text))
    return {
        match.group(1): jobs_text[match.start() : matches[index + 1].start()]
        if index + 1 < len(matches)
        else jobs_text[match.start() :]
        for index, match in enumerate(matches)
    }


def check_topology(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    sections = _job_sections(text)
    if set(sections) != EXPECTED_JOBS:
        raise ValueError(
            f"CI jobs differ from frozen topology: {sorted(sections)}"
        )

    for job in ("runtime-evidence", "controlled-rejections"):
        if "    needs: core-contracts\n" not in sections[job]:
            raise ValueError(f"{job} must depend on core-contracts")

    for step, expected_owner in STEP_OWNERS.items():
        owners = {
            job for job, section in sections.items() if f"- name: {step}\n" in section
        }
        expected = (
            {expected_owner} if isinstance(expected_owner, str) else expected_owner
        )
        if owners != expected:
            raise ValueError(
                f"CI step {step!r} owners {sorted(owners)} != {sorted(expected)}"
            )

    rejection_count = sections["controlled-rejections"].count(
        "        continue-on-error: true\n"
    )
    if rejection_count != 4:
        raise ValueError("controlled-rejections must contain four expected failures")
    for job, section in sections.items():
        if job != "controlled-rejections" and "continue-on-error: true" in section:
            raise ValueError(f"Unexpected continue-on-error outside rejection job: {job}")

    if "actions/download-artifact" in text:
        raise ValueError("CI jobs must rebuild prerequisites, not share mutable artifacts")

    return {
        "job_count": len(sections),
        "matrix_job_count": sum("matrix:" in section for section in sections.values()),
        "controlled_failure_count": rejection_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen CI job topology")
    parser.add_argument(
        "path", nargs="?", type=Path, default=Path(".github/workflows/ci.yml")
    )
    args = parser.parse_args()
    result = check_topology(args.path)
    print(
        "valid CI topology: "
        f"{result['job_count']} jobs, {result['matrix_job_count']} matrices, "
        f"{result['controlled_failure_count']} controlled failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
