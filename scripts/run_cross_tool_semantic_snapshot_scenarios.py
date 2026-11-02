"""Build an isolated synthetic ECUC project and exercise semantic snapshot gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from automotive_workbench.cross_tool_acceptance import assess_acceptance, verify_acceptance
from automotive_workbench.cross_tool_trace import compare_traces, trace_cross_tool
from automotive_workbench.project_ecuc import capture, run
from tests.test_cross_tool_acceptance import scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    engineering = output / "engineering"
    engineering.mkdir()
    impact, bindings, _, _, _ = scenario(engineering)
    declaration = {
        "schema_version": "workbench-project-0.6", "name": "Demo acceptance",
        "comparison_key": "cross-tool-snapshot-test",
        "inputs": {role: {"project": f"{side}/demo.dpa", "applications": [], "tool_logs": []}
                   for role, side in (("baseline", "before"), ("candidate", "after"))},
        "requirements": [{"id": "TX_VECTOR", "text": "Communication structure", "stage": "ecuc",
                          "pointer": "/checks/communication/status", "expected": "passed"}],
    }
    project = engineering / "test.project.json"
    project.write_text(json.dumps(declaration, indent=2) + "\n", encoding="utf-8")
    package = output / "project-package"
    run(declaration, capture(project, declaration, project.read_bytes()), package)
    report = package / "bundle/project-report.json"
    positive_path = output / "semantic-positive.json"
    positive = assess_acceptance(impact, bindings, report, positive_path, strict_semantics=True)
    if positive["status"] != "rerun-required" or verify_acceptance(positive_path)["status"] != "passed":
        raise ValueError("Positive semantic snapshot scenario failed")

    unresolved_engineering = output / "unresolved-engineering"
    unresolved_engineering.mkdir()
    unresolved_impact, unresolved_bindings, _, _, _ = scenario(unresolved_engineering)
    system = unresolved_engineering / "after/system.arxml"
    system.write_bytes(system.read_bytes().replace(b"/Signal/Alternate", b"/Signal/Unknown"))
    trace_cross_tool(unresolved_engineering / "after/mapping.json", system,
                     unresolved_engineering / "after/demo.dpa", unresolved_engineering / "after/trace.json")
    compare_traces(unresolved_engineering / "before/trace.json", unresolved_engineering / "after/trace.json", unresolved_impact)
    unresolved_path = output / "semantic-unresolved.json"
    unresolved = assess_acceptance(unresolved_impact, unresolved_bindings, report, unresolved_path, strict_semantics=True)
    if unresolved["status"] != "attention-required":
        raise ValueError("Unresolved Developer mapping was not reported")
    drift_engineering = output / "drift-engineering"
    drift_engineering.mkdir()
    drift_impact, drift_bindings, _, _, _ = scenario(drift_engineering)
    module = drift_engineering / "after/modules.arxml"
    module.write_bytes(module.read_bytes().replace(b"ComSystemTemplateSystemSignalRef", b"ComSystemTemplateOtherRef"))
    trace_cross_tool(drift_engineering / "after/mapping.json", drift_engineering / "after/system.arxml",
                     drift_engineering / "after/demo.dpa", drift_engineering / "after/trace.json")
    compare_traces(drift_engineering / "before/trace.json", drift_engineering / "after/trace.json", drift_impact)
    try:
        assess_acceptance(drift_impact, drift_bindings, report, output / "invalid.json", strict_semantics=True)
    except ValueError as exc:
        if "after ECUC source modules.arxml differs" not in str(exc):
            raise
        drift_error = str(exc)
    else:
        raise ValueError("Drifted ECUC module was accepted")
    summary = {"contract_version": "cross-tool-semantic-scenarios-0.1",
               "status": "passed", "positive": positive["status"],
               "unresolved": unresolved["status"], "module_drift": drift_error,
               "scope": "Synthetic Developer/System/ECUC structure and project snapshot; no vendor generation or CAN runtime"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
