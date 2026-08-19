from __future__ import annotations

import copy
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from automotive_workbench.adapters.canonical_contract import validate_contract_mapping
from automotive_workbench.adapters.dbc import validate_dbc_intent


@dataclass(frozen=True)
class Scenario:
    name: str
    expected_codes: tuple[str, ...]
    mutate_intent: Callable[[dict[str, Any]], None] | None = None
    mutate_contract: Callable[[dict[str, Any]], None] | None = None


def _set_intent(path: tuple[str | int, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        target: Any = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


SCENARIOS = (
    Scenario("baseline", ()),
    Scenario("intent_dlc_mismatch", ("DBC-DLC-MISMATCH",), mutate_intent=_set_intent(("messages", 0, "dlc"), 7)),
    Scenario("intent_start_bit_mismatch", ("DBC-SIGNAL-PROPERTY-MISMATCH",), mutate_intent=_set_intent(("signals", 0, "start_bit"), 1)),
    Scenario("contract_scale_mismatch", ("MAP-NUMERIC-MISMATCH",), mutate_contract=_set_intent(("signals", 0, "resolution"), "0.5")),
    Scenario("contract_unit_mismatch", ("MAP-UNIT-MISMATCH",), mutate_contract=_set_intent(("signals", 0, "unit"), "mm")),
    Scenario("contract_range_mismatch", ("MAP-RANGE-MISMATCH",), mutate_contract=_set_intent(("signals", 0, "physical_range"), "0-200")),
)


def _run_scenario(
    scenario: Scenario,
    dbc: Path,
    base_intent: dict[str, Any],
    base_contract: dict[str, Any],
    directory: Path,
) -> dict[str, Any]:
    intent = copy.deepcopy(base_intent)
    contract = copy.deepcopy(base_contract)
    if scenario.mutate_intent:
        scenario.mutate_intent(intent)
    if scenario.mutate_contract:
        scenario.mutate_contract(contract)
    intent_path = directory / f"{scenario.name}.intent.json"
    contract_path = directory / f"{scenario.name}.contract.json"
    intent_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    started = time.perf_counter()
    validations = (
        validate_dbc_intent(dbc, intent_path),
        validate_contract_mapping(dbc, contract_path, intent_path),
    )
    elapsed = round((time.perf_counter() - started) * 1000)
    findings = [finding for validation in validations for finding in validation["findings"]]
    for finding in findings:
        if finding["source_artifact"] == str(intent_path):
            finding["source_artifact"] = f"scenario-input://{scenario.name}/intent"
        elif finding["source_artifact"] == str(contract_path):
            finding["source_artifact"] = f"scenario-input://{scenario.name}/contract"
    actual_codes = {finding["code"] for finding in findings}
    expected_codes = set(scenario.expected_codes)
    passed = expected_codes.issubset(actual_codes) and (
        bool(expected_codes) or not findings
    )
    return {
        "scenario": scenario.name,
        "status": "passed" if passed else "failed",
        "expectation": "no findings" if not expected_codes else f"contains {', '.join(scenario.expected_codes)}",
        "duration_ms": elapsed,
        "finding_count": len(findings),
        "finding_codes": sorted(actual_codes),
        "findings": findings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Automotive Workbench Experiment Report",
        "",
        f"- Run ID: `{result['run_id']}`",
        f"- Status: **{result['status']}**",
        f"- Scenarios: {result['passed_count']}/{result['scenario_count']} passed",
        f"- Duration: {result['duration_ms']} ms",
        "",
        "| Scenario | Result | Expected | Findings |",
        "|---|---|---|---:|",
    ]
    for scenario in result["scenarios"]:
        lines.append(
            f"| `{scenario['scenario']}` | {scenario['status']} | {scenario['expectation']} | {scenario['finding_count']} |"
        )
    lines.extend(["", "## Findings", ""])
    for scenario in result["scenarios"]:
        if not scenario["findings"]:
            continue
        lines.append(f"### {scenario['scenario']}")
        lines.append("")
        for finding in scenario["findings"]:
            lines.append(f"- `{finding['code']}` — {finding['message']}")
        lines.append("")
    lines.extend([
        "## Boundary",
        "",
        "This report proves deterministic consistency checks for public artifacts. It does not prove vendor ECUC generation or production BSW configuration validity.",
        "",
    ])
    return "\n".join(lines)


def run_suite(dbc: Path, contract: Path, intent: Path, output: Path) -> dict[str, Any]:
    started = time.perf_counter()
    base_intent = json.loads(intent.read_text(encoding="utf-8-sig"))
    base_contract = json.loads(contract.read_text(encoding="utf-8-sig"))
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        scenarios = [
            _run_scenario(scenario, dbc, base_intent, base_contract, directory)
            for scenario in SCENARIOS
        ]
    passed_count = sum(scenario["status"] == "passed" for scenario in scenarios)
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "experiment-suite",
        "run_id": timestamp.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": timestamp.isoformat(),
        "status": "passed" if passed_count == len(scenarios) else "failed",
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "artifacts": [str(dbc), str(contract), str(intent)],
        "scenarios": scenarios,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "experiment-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "experiment-report.md").write_text(render_markdown(result), encoding="utf-8")
    return result
