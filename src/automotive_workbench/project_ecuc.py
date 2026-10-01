"""Declarative static ECUC acceptance, reusing the P26 snapshot consumers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from automotive_workbench import __version__
from automotive_workbench.ecuc_impact import compute, verify_impact
from automotive_workbench.ecuc_model import canonical
from automotive_workbench.ecuc_project import sha
from automotive_workbench.ecuc_review import build, check_output, read_verified, render
from automotive_workbench.evidence_bundle import (
    create_evidence_bundle_manifest,
    verify_evidence_bundle,
)

VERSION = "workbench-project-0.6"
REPORT_VERSION = "project-acceptance-0.6"
ENGINE = "ecuc-project-acceptance-0.1"
CHECKS = ("communication", "application", "task_bindings", "mode_rules", "impact")
SCOPE = [
    "Only explicitly declared static acceptance checks gate this project; omitted domains are not accepted.",
    "Missing coverage is unassessed; a recorded structural gap fails the declared check, not vendor validity.",
    "Historical logs cannot pass or fail current checks. Runtime timing, vendor generation and physical ECU behavior are outside scope.",
]


def encoded(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def declaration(project: Any) -> dict[str, Any]:
    if (
        not isinstance(project, dict)
        or set(project)
        != {"schema_version", "name", "comparison_key", "inputs", "requirements"}
        or project.get("schema_version") != VERSION
    ):
        raise ValueError(
            "ECUC project requires closed workbench-project-0.6 declaration"
        )
    for field in ("name", "comparison_key"):
        if not isinstance(project[field], str) or not project[field].strip():
            raise ValueError(f"ECUC project {field} must be nonempty")
    inputs = project["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"baseline", "candidate"}:
        raise ValueError("ECUC project requires baseline and candidate")
    for item in inputs.values():
        if not isinstance(item, dict) or set(item) != {
            "project",
            "applications",
            "tool_logs",
        }:
            raise ValueError(
                "ECUC input must declare project, applications and tool_logs"
            )
        if not isinstance(item["project"], str) or not item["project"].strip():
            raise ValueError("ECUC project path must be nonempty")
        for key in ("applications", "tool_logs"):
            if (
                not isinstance(item[key], list)
                or any(not isinstance(x, str) or not x.strip() for x in item[key])
                or len(set(item[key])) != len(item[key])
            ):
                raise ValueError(
                    "ECUC additional paths must be unique nonempty strings"
                )
    requirements = project["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("ECUC acceptance requires explicit checks")
    ids: set[str] = set()
    pointers: set[str] = set()
    for item in requirements:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "text",
            "stage",
            "pointer",
            "expected",
        }:
            raise ValueError(
                "ECUC requirement requires id, text, stage, pointer, expected"
            )
        if (
            not isinstance(item["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", item["id"])
            or item["id"] in ids
        ):
            raise ValueError("ECUC requirement IDs must be unique portable identifiers")
        if not isinstance(item["text"], str) or not item["text"].strip():
            raise ValueError("ECUC requirement text must be nonempty")
        if (
            item["stage"] != "ecuc"
            or item["expected"] != "passed"
            or not isinstance(item["pointer"], str)
            or item["pointer"] not in {f"/checks/{c}/status" for c in CHECKS}
        ):
            raise ValueError("ECUC requirement must demand a supported check passes")
        if item["pointer"] in pointers:
            raise ValueError("Duplicate ECUC check")
        ids.add(item["id"])
        pointers.add(item["pointer"])
    return project


def capture(path: Path, project: dict[str, Any], raw: bytes) -> dict[str, bytes]:
    declaration(project)
    snapshots = {"inputs/project.json": raw}
    for role, side in (("baseline", "before"), ("candidate", "after")):
        item = project["inputs"][role]
        report, sources = build(
            path.parent / item["project"],
            [path.parent / x for x in item["applications"]],
            [path.parent / x for x in item["tool_logs"]],
        )
        prefix = f"ecuc/{side}/"
        snapshots[prefix + "ecuc-review.json"] = encoded(report)
        snapshots[prefix + "index.html"] = render(
            "ECUC engineering review", report
        ).encode()
        snapshots.update({prefix + "snapshot/" + k: v for k, v in sources.items()})
    return snapshots


def aggregate(statuses: list[str]) -> str:
    for status in ("failed", "blocked", "unassessed"):
        if status in statuses:
            return status
    return "passed"


def stage_report(
    project: dict[str, Any], before: dict, after: dict, impact: dict
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for name in CHECKS:
        path, pointer = "ecuc/after/ecuc-review.json", "/integration"
        affected: set[str] = set()
        if name == "impact":
            path, pointer = "ecuc/ecuc-impact.json", "/status"
            status = (
                "blocked"
                if impact["status"] == "not-comparable"
                else "unassessed"
                if impact["status"] == "partial"
                or any(impact["unresolved_dependency_counts"].values())
                else "passed"
            )
            reason = {
                "blocked": "snapshots_not_comparable",
                "unassessed": "impact_coverage_incomplete",
                "passed": "explicit_dependencies_assessed",
            }[status]
            affected.update(x["object_id"] for x in impact["affected_objects"])
        elif name == "communication":
            pointer = "/communication"
            comm = after["communication"]
            status = (
                "unassessed"
                if not comm["paths"]
                else "passed"
                if comm["status"] == "resolved-in-scope"
                else "failed"
            )
            reason = (
                "coverage_missing"
                if status == "unassessed"
                else "structural_gap"
                if status == "failed"
                else "linked_in_scope"
            )
            affected.update(
                n
                for x in impact["communication_impacts"]
                for n in x["affected_members"]
            )
        else:
            section = {
                "application": "applications",
                "task_bindings": "bindings",
                "mode_rules": "mode_rules",
            }[name]
            pointer += "/" + section
            rows = after["integration"][section]
            status = (
                "failed"
                if any(x["status"] == "partial" for x in rows)
                else "unassessed"
                if after["integration"]["coverage"][name] == "unassessed" or not rows
                else "passed"
            )
            # Explicit application absence is a coverage gap even if dependent task checks fail.
            if (
                name == "application"
                and after["integration"]["coverage"][name] == "unassessed"
            ):
                status = "unassessed"
            if name == "task_bindings" and rows and not after["inputs"]["applications"]:
                status = "unassessed"
            reason = (
                "coverage_missing"
                if status == "unassessed"
                else "structural_gap"
                if status == "failed"
                else "linked_in_scope"
            )
            if name == "application":
                affected.update(
                    x["object_id"]
                    for x in impact["affected_objects"]
                    if x["object_id"].startswith("application:")
                )
            else:
                key = "binding_impacts" if name == "task_bindings" else "mode_impacts"
                affected.update(n for x in impact[key] for n in x["affected_members"])
        checks[name] = {
            "status": status,
            "reason": reason,
            "evidence": {"path": path, "pointer": pointer},
            "affected_objects": sorted(affected),
        }
    selected = [x["pointer"].split("/")[2] for x in project["requirements"]]
    return {
        "schema_version": ENGINE,
        "status": aggregate([checks[n]["status"] for n in selected]),
        "scope": SCOPE,
        "producer": {"engine": ENGINE, "workbench_version": __version__},
        "selected_checks": selected,
        "checks": checks,
        "summary": {
            "changed_objects": impact["summary"]["changed_objects"],
            "affected_objects": impact["summary"]["affected_objects"],
        },
    }


def project_report(
    project: dict[str, Any], stage: dict[str, Any], bundle: Path
) -> dict[str, Any]:
    requirements = []
    for item in project["requirements"]:
        check = stage["checks"][item["pointer"].split("/")[2]]
        requirements.append(
            {
                **item,
                "status": check["status"],
                "reason": check["reason"],
                "actual": check["status"],
                "evidence": {
                    "path": "ecuc-stage.json",
                    "pointer": item["pointer"],
                    "sha256": sha((bundle / "ecuc-stage.json").read_bytes()),
                },
            }
        )
    return {
        "artifact_type": "project-acceptance",
        "schema_version": REPORT_VERSION,
        "name": project["name"],
        "status": stage["status"],
        "stages": {"ecuc": {"status": stage["status"], "path": "ecuc-stage.json"}},
        "requirements": requirements,
        "comparison_basis": {
            "comparison_key": project["comparison_key"],
            "engine": ENGINE,
            "baseline_sha256": sha(
                (bundle / "ecuc/before/ecuc-review.json").read_bytes()
            ),
        },
        "source_artifacts": [
            {
                "source": "bundle/" + p.relative_to(bundle).as_posix(),
                "sha256": sha(p.read_bytes()),
            }
            for p in sorted(bundle.rglob("*"))
            if p.is_file()
            and p not in {bundle / "project-report.json", bundle / "index.html"}
        ],
    }


def render_project(report: dict[str, Any]) -> str:
    from automotive_workbench.project_workflow import _render_html

    return _render_html(report).replace(
        "通信实验验证所选 python-can 后端上的应用层行为，不证明目标 ECU 或量产配置。",
        "本项目只执行静态 ECUC 检查；未声明项不算通过，历史日志不代表当前失败，亦不证明实时调度、厂商生成或物理 ECU。",
    )


def run(
    project: dict[str, Any], snapshots: dict[str, bytes], output: Path
) -> dict[str, Any]:
    check_output(output)
    output = output.resolve()
    bundle = output / "bundle"
    for name, raw in snapshots.items():
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    before_path, after_path = [
        bundle / f"ecuc/{s}/ecuc-review.json" for s in ("before", "after")
    ]
    before, after = read_verified(before_path), read_verified(after_path)
    impact = compute(
        before, after, sha(before_path.read_bytes()), sha(after_path.read_bytes())
    )
    (bundle / "ecuc/ecuc-impact.json").write_bytes(encoded(impact))
    (bundle / "ecuc/index.html").write_text(
        render("ECUC configuration impact", impact), encoding="utf-8"
    )
    stage = stage_report(project, before, after, impact)
    (bundle / "ecuc-stage.json").write_bytes(encoded(stage))
    report = project_report(project, stage, bundle)
    (bundle / "project-report.json").write_bytes(encoded(report))
    (bundle / "index.html").write_text(render_project(report), encoding="utf-8")
    validate(bundle / "project-report.json", report)
    create_evidence_bundle_manifest(
        bundle, output / "manifest.json", "workbench run-project ECUC 0.6", base=output
    )
    verification = verify_evidence_bundle(
        bundle, output / "manifest.json", output / "verification", base=output
    )
    return {
        "status": report["status"] if verification["status"] == "passed" else "failed",
        "project_status": report["status"],
        "integrity_status": verification["status"],
        "report": str(bundle / "index.html"),
        "report_json": str(bundle / "project-report.json"),
    }


def validate(path: Path, report: dict[str, Any]) -> None:
    bundle = path.parent
    if (
        bundle.is_symlink()
        or path.name != "project-report.json"
        or path.is_symlink()
        or any(p.is_symlink() for p in bundle.rglob("*"))
    ):
        raise ValueError("ECUC project inventory must not contain symlinks")
    project = declaration(
        json.loads((bundle / "inputs/project.json").read_text(encoding="utf-8-sig"))
    )
    if {p.name for p in bundle.iterdir()} != {
        "inputs",
        "ecuc",
        "ecuc-stage.json",
        "project-report.json",
        "index.html",
    } or {p.name for p in (bundle / "inputs").iterdir()} != {"project.json"}:
        raise ValueError("ECUC project inventory differs")
    verify_impact(bundle / "ecuc/ecuc-impact.json")
    before, after = [
        json.loads(
            (bundle / f"ecuc/{side}/ecuc-review.json").read_text(encoding="utf-8")
        )
        for side in ("before", "after")
    ]
    for role, review in (("baseline", before), ("candidate", after)):
        for key in ("applications", "tool_logs"):
            if len(project["inputs"][role][key]) != len(review["inputs"][key]):
                raise ValueError("Captured ECUC input count differs from declaration")
    impact = json.loads((bundle / "ecuc/ecuc-impact.json").read_text(encoding="utf-8"))
    stage = stage_report(project, before, after, impact)
    if canonical(
        json.loads((bundle / "ecuc-stage.json").read_text(encoding="utf-8"))
    ) != canonical(stage):
        raise ValueError("ECUC acceptance stage differs from replay")
    expected = project_report(project, stage, bundle)
    if canonical(report) != canonical(expected) or (bundle / "index.html").read_text(
        encoding="utf-8"
    ) != render_project(expected):
        raise ValueError("ECUC project differs from replay")


def verify(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != REPORT_VERSION:
        raise ValueError("verify-ecuc-project requires project-acceptance-0.6")
    validate(path, report)
    return {
        "status": "passed",
        "project_status": report["status"],
        "report_sha256": sha(path.read_bytes()),
    }
