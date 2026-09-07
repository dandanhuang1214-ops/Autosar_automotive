from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _escape_workflow_command(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


class AnnotatingTestResult(unittest.TextTestResult):
    def _annotate(self, kind: str, test: unittest.TestCase, error: Any) -> None:
        detail = self._exc_info_to_string(error, test)
        title = _escape_workflow_command(f"Unit test {kind}: {test.id()}")
        message = _escape_workflow_command(detail[-4000:])
        print(f"::error title={title}::{message}")

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        self._annotate("failure", test, err)

    def addError(self, test: unittest.TestCase, err: Any) -> None:
        super().addError(test, err)
        self._annotate("error", test, err)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run unittest discovery with machine-readable CI failure evidence"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    suite = unittest.defaultTestLoader.discover("tests")
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=AnnotatingTestResult,
    )
    result = runner.run(suite)
    summary = {
        "artifact_type": "workbench-ci-test-summary",
        "schema_version": "ci-test-summary-1.0",
        "status": "passed" if result.wasSuccessful() else "failed",
        "tests_run": result.testsRun,
        "failure_tests": [test.id() for test, _ in result.failures],
        "error_tests": [test.id() for test, _ in result.errors],
        "skipped_tests": [test.id() for test, _ in result.skipped],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ci-test-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
