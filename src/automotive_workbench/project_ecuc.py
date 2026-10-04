"""Declarative static ECUC acceptance, reusing the P26 snapshot consumers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from automotive_workbench import __version__
from automotive_workbench.can_io import BusConfig
from automotive_workbench.ecuc_impact import compute, verify_impact
from automotive_workbench.ecuc_model import canonical
from automotive_workbench.ecuc_policy import evaluate, validate_policies
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
    modern = isinstance(project, dict) and project.get("schema_version") in (
        "workbench-project-0.7",
        "workbench-project-0.8",
        "workbench-project-0.9",
    )
    linked = (
        isinstance(project, dict)
        and project.get("schema_version") == "workbench-project-0.8"
    )
    diagnostic = (
        isinstance(project, dict)
        and project.get("schema_version") == "workbench-project-0.9"
    )
    if (
        not isinstance(project, dict)
        or set(project)
        != (
            {"schema_version", "name", "comparison_key", "inputs", "requirements"}
            | ({"policies"} if modern else set())
            | ({"runtime"} if linked else set())
            | ({"diagnostic"} if diagnostic else set())
        )
        or project.get("schema_version")
        not in (
            VERSION,
            "workbench-project-0.7",
            "workbench-project-0.8",
            "workbench-project-0.9",
        )
    ):
        raise ValueError(
            "ECUC project requires closed workbench-project-0.6/0.7/0.8/0.9 declaration"
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
    policy_ids = validate_policies(project["policies"]) if modern else set()
    allowed = {f"/checks/{c}/status" for c in CHECKS} | {
        f"/checks/policy.{i}/status" for i in policy_ids
    }
    runtime_ids: set[str] = set()
    if linked:
        from automotive_workbench.ecuc_runtime import declaration as runtime_declaration

        runtime_ids = runtime_declaration(project["runtime"], project["policies"])
        allowed |= {f"/checks/runtime.{i}/status" for i in runtime_ids}
    diagnostic_ids: set[str] = set()
    if diagnostic:
        from automotive_workbench.ecuc_diagnostic import (
            declaration as diagnostic_declaration,
        )

        diagnostic_ids = diagnostic_declaration(project["diagnostic"], policy_ids)
        allowed |= {f"/checks/diagnostic.{i}/status" for i in diagnostic_ids}
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
            or item["pointer"] not in allowed
        ):
            raise ValueError("ECUC requirement must demand a supported check passes")
        if item["pointer"] in pointers:
            raise ValueError("Duplicate ECUC check")
        ids.add(item["id"])
        pointers.add(item["pointer"])
    if any(f"/checks/policy.{i}/status" not in pointers for i in policy_ids):
        raise ValueError(
            "Every object policy must be a mandatory acceptance requirement"
        )
    if any(f"/checks/runtime.{i}/status" not in pointers for i in runtime_ids):
        raise ValueError("Every runtime binding must be a mandatory requirement")
    if any(f"/checks/diagnostic.{i}/status" not in pointers for i in diagnostic_ids):
        raise ValueError("Every diagnostic dependency must be a mandatory requirement")
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
    if "runtime" in project:
        from automotive_workbench.ecuc_runtime import capture as capture_runtime

        snapshots.update(capture_runtime(path, project))
    if "diagnostic" in project:
        from automotive_workbench.ecuc_diagnostic import capture as capture_diagnostic

        snapshots.update(capture_diagnostic(path, project))
    return snapshots


def aggregate(statuses: list[str]) -> str:
    for status in ("failed", "blocked", "unassessed"):
        if status in statuses:
            return status
    return "passed"


def stage_report(
    project: dict[str, Any],
    before: dict,
    after: dict,
    impact: dict,
    runtime_checks: dict | None = None,
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
    for policy in project.get("policies", []):
        checks["policy." + policy["id"]] = evaluate(policy, before, after, impact)
    engine = "ecuc-project-acceptance-0.2" if "policies" in project else ENGINE
    selected = [x["pointer"].split("/")[2] for x in project["requirements"]]
    if "runtime" in project:
        if runtime_checks is None:
            selected = [n for n in selected if not n.startswith("runtime.")]
        else:
            checks.update(runtime_checks)
            engine = "ecuc-project-acceptance-0.3"
    if "diagnostic" in project:
        if runtime_checks is None:
            selected = [n for n in selected if not n.startswith("diagnostic.")]
        else:
            checks.update(runtime_checks)
            engine = "ecuc-project-acceptance-0.4"
    return {
        "schema_version": engine,
        "status": aggregate([checks[n]["status"] for n in selected]),
        "scope": SCOPE
        if "diagnostic" not in project
        else [
            "Explicit configuration acceptance dependency on an independent read-only diagnostic execution.",
            "No Dcm/CanTp semantic mapping, generated-code provenance, physical ECU or ECU authentication is inferred.",
        ],
        "producer": {"engine": engine, "workbench_version": __version__},
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
    from automotive_workbench.ecuc_diagnostic import comparison_basis

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
        "schema_version": project["schema_version"].replace(
            "workbench-project", "project-acceptance"
        ),
        "name": project["name"],
        "status": stage["status"],
        "stages": {"ecuc": {"status": stage["status"], "path": "ecuc-stage.json"}},
        "requirements": requirements,
        "comparison_basis": {
            "comparison_key": project["comparison_key"],
            "engine": stage["schema_version"],
            **(
                {"policy_sha256": sha(canonical(project["policies"]).encode())}
                if "policies" in project
                else {}
            ),
            **(
                {"runtime_basis": runtime_basis(project, bundle)}
                if "runtime" in project
                else {}
            ),
            **(
                {"diagnostic_basis": comparison_basis(project, bundle)}
                if "diagnostic" in project
                else {}
            ),
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

    if report["schema_version"] == "project-acceptance-0.9":
        return _render_html(report).replace(
            "通信实验验证所选 python-can 后端上的应用层行为，不证明目标 ECU 或量产配置。",
            "本项目要求配置策略通过后执行独立只读诊断；显式验收依赖不证明 Dcm/CanTp 语义映射、配置生成代码或物理 ECU。",
        )
    if report["schema_version"] == "project-acceptance-0.8":
        return _render_html(report).replace(
            "通信实验验证所选 python-can 后端上的应用层行为，不证明目标 ECU 或量产配置。",
            "本项目关联静态 ECUC 策略与同次 CAN 向量观测；显式合成映射不证明厂商生成 BSW、独立 ECU、可调度性或物理 ECU。",
        )
    return _render_html(report).replace(
        "通信实验验证所选 python-can 后端上的应用层行为，不证明目标 ECU 或量产配置。",
        "本项目只执行静态 ECUC 检查；未声明项不算通过，历史日志不代表当前失败，亦不证明实时调度、厂商生成或物理 ECU。",
    )


def run(
    project: dict[str, Any],
    snapshots: dict[str, bytes],
    output: Path,
    *,
    config: BusConfig | None = None,
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
    if "runtime" in project:
        from automotive_workbench.ecuc_runtime import execute, replay

        if config is None:
            raise ValueError("Linked project requires explicit backend conditions")
        execute(bundle, project, after, stage, config)
        stage = stage_report(
            project, before, after, impact, replay(bundle, project, after, stage)
        )
    if "diagnostic" in project:
        from automotive_workbench.ecuc_diagnostic import (
            execute as diagnostic_execute,
            replay as diagnostic_replay,
        )

        if config is None:
            raise ValueError("Diagnostic project requires explicit backend conditions")
        diagnostic_execute(bundle, project, stage, config)
        stage = stage_report(
            project, before, after, impact, diagnostic_replay(bundle, project, stage)
        )
    (bundle / "ecuc-stage.json").write_bytes(encoded(stage))
    report = project_report(project, stage, bundle)
    (bundle / "project-report.json").write_bytes(encoded(report))
    (bundle / "index.html").write_text(render_project(report), encoding="utf-8")
    validate(bundle / "project-report.json", report)
    create_evidence_bundle_manifest(
        bundle,
        output / "manifest.json",
        "workbench run-project ECUC " + project["schema_version"].rsplit("-", 1)[-1],
        base=output,
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
    roots = {
        "inputs",
        "ecuc",
        "ecuc-stage.json",
        "project-report.json",
        "index.html",
    }
    input_names = {"project.json"}
    if "runtime" in project:
        from automotive_workbench.ecuc_runtime import FILES

        roots.add("runtime-link.json")
        if (bundle / "runtime").exists():
            roots.add("runtime")
            if {p.name for p in (bundle / "runtime").iterdir()} != {
                "declared-runtime-report.json",
                "declared-runtime-report.md",
            }:
                raise ValueError("Runtime inventory differs")
        input_names.update(FILES.values())
    if "diagnostic" in project:
        from automotive_workbench.ecuc_diagnostic import input_inventory

        roots.add("diagnostic-link.json")
        if (bundle / "external-ecu").exists():
            roots.add("external-ecu")
        input_names.update(input_inventory(bundle))
    if {p.name for p in bundle.iterdir()} != roots or {
        p.name for p in (bundle / "inputs").iterdir()
    } != input_names:
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
    if "runtime" in project:
        from automotive_workbench.ecuc_runtime import replay

        stage = stage_report(
            project, before, after, impact, replay(bundle, project, after, stage)
        )
    if "diagnostic" in project:
        from automotive_workbench.ecuc_diagnostic import replay as diagnostic_replay

        stage = stage_report(
            project, before, after, impact, diagnostic_replay(bundle, project, stage)
        )
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
    if not isinstance(report, dict) or report.get("schema_version") not in (
        REPORT_VERSION,
        "project-acceptance-0.7",
        "project-acceptance-0.8",
        "project-acceptance-0.9",
    ):
        raise ValueError(
            "verify-ecuc-project requires project-acceptance-0.6/0.7/0.8/0.9"
        )
    validate(path, report)
    return {
        "status": "passed",
        "project_status": report["status"],
        "report_sha256": sha(path.read_bytes()),
    }


def runtime_basis(project: dict, bundle: Path) -> str:
    from automotive_workbench.ecuc_runtime import FILES

    record = json.loads((bundle / "runtime-link.json").read_text(encoding="utf-8"))
    return sha(
        canonical(
            {
                "declaration": project["runtime"],
                "inputs": {
                    k: sha((bundle / "inputs" / v).read_bytes())
                    for k, v in FILES.items()
                },
                "backend": record["requested_config"],
            }
        ).encode()
    )
