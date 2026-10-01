"""Portable ECUC engineering review: current structure and separate historical logs."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from automotive_workbench.ecuc_communication import build_model
from automotive_workbench.ecuc_integration import analyze
from automotive_workbench.ecuc_model import (
    application_objects,
    canonical,
    ecuc_objects,
    prefix_sources,
)
from automotive_workbench.ecuc_project import (
    MAX_FILE,
    MAX_TOTAL,
    read_project,
    safe_file,
    sha,
)

VERSION = "ecuc-engineering-review-0.1"
SCOPE = [
    "Selected ECUC plus explicitly supplied application ARXML; no directory discovery or implicit ECU Extract completeness.",
    "Application prototypes/type ownership, RTE event/task references and BswM structure only.",
    "Missing task binding is an evidence gap, not a claim that the vendor configuration is invalid.",
    "Periods, activation/priority/WCET, mode behavior, vendor generation and physical ECU execution are unassessed.",
    "Tool logs are historical unbound observations; exact object-path association is not current failure or root-cause proof.",
]
LOG_LINE = re.compile(r"^(ERROR|WARNING|INFO)\s+(\S+)\s+\[(/[^\]]*)\]\s+(.*)$")


def check_output(output: Path, project: Path | None = None) -> None:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("Output must be empty or absent and not a symlink")
    if project and output.resolve().is_relative_to(project.resolve().parent):
        raise ValueError("Review output must be outside the source project")


def render(title: str, report: dict[str, Any]) -> str:
    """Deterministic, offline HTML; escape all imported data."""
    esc = html.escape
    sections = []
    overview = (
        "<table><tbody>"
        + "".join(
            '<tr><th style="text-align:left;padding:.3rem 1rem .3rem 0">'
            + esc(k.replace("_", " "))
            + "</th><td>"
            + esc(str(v))
            + "</td></tr>"
            for k, v in report.get("summary", {}).items()
        )
        + "</tbody></table>"
    )
    if "integration" in report:
        rows = [
            *(
                ("Application", x["instance"], x["status"], x["gaps"])
                for x in report["integration"]["applications"]
            ),
            *(
                ("Task binding", x["mapping"], x["status"], x["gaps"])
                for x in report["integration"]["bindings"]
            ),
            *(
                ("Mode rule", x["rule"], x["status"], x["gaps"])
                for x in report["integration"]["mode_rules"]
            ),
        ]
        overview += (
            "<h2>Current structural checks</h2><table><tr><th>Check</th><th>Object</th><th>Status</th><th>Gaps</th></tr>"
            + "".join(
                "<tr>"
                + "".join(
                    '<td style="padding:.4rem;border-bottom:1px solid #ddd">'
                    + esc(str(v))
                    + "</td>"
                    for v in (kind, identity, status, "; ".join(gaps))
                )
                + "</tr>"
                for kind, identity, status, gaps in rows
            )
            + "</table>"
        )
    if "changes" in report:
        overview += (
            "<h2>Configuration changes</h2><table><tr><th>Object</th><th>Change</th><th>Fields</th></tr>"
            + "".join(
                "<tr>"
                + "".join(
                    '<td style="padding:.4rem">' + esc(v) + "</td>"
                    for v in (x["object_id"], x["kind"], ", ".join(x["fields"]))
                )
                + "</tr>"
                for x in report["changes"]
            )
            + "</table>"
        )
    display = dict(report)
    display.pop("objects", None)
    if "communication" in display:
        display["communication"] = {
            "status": report["communication"]["status"],
            "paths": [
                {
                    k: p[k]
                    for k in (
                        "com_ipdu",
                        "direction",
                        "route",
                        "canif_pdu",
                        "status",
                        "gaps",
                    )
                }
                for p in report["communication"]["paths"]
            ],
            "inspection_findings": report["communication"]["inspection_findings"],
        }
        display["integration"] = {
            k: report["integration"][k] for k in ("coverage", "findings")
        }
    for key, value in display.items():
        if key in {"schema_version", "status", "scope"}:
            continue
        if isinstance(value, list) and len(value) > 1000:
            value = {
                "shown": value[:1000],
                "total": len(value),
                "note": "Display limited to 1000 rows; complete data is in the JSON report.",
            }
        sections.append(
            f"<details><summary>{esc(key)}</summary><pre>{esc(json.dumps(value, ensure_ascii=False, indent=2))}</pre></details>"
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>'
        + esc(title)
        + "</title>"
        "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f6f8fa;color:#17212b}"
        "details{background:white;border:1px solid #d0d7de;padding:1rem;margin:1rem 0}summary{cursor:pointer;font-weight:600}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}li{margin:.5rem 0}</style>"
        "<h1>"
        + esc(title)
        + "</h1><p>Status: <strong>"
        + esc(report["status"])
        + "</strong></p><ul>"
        + "".join("<li>" + esc(s) + "</li>" for s in report["scope"])
        + "</ul>"
        + overview
        + '<p><a href="'
        + ("ecuc-review.json" if "integration" in report else "ecuc-impact.json")
        + '">Complete JSON evidence and source locations</a></p>'
        + "".join(sections)
        + "</html>\n"
    )


def build(
    project: Path, applications: list[Path], logs: list[Path]
) -> tuple[dict[str, Any], dict[str, bytes]]:
    inspection, project_sources, containers = read_project(project)
    communication = prefix_sources(build_model(inspection, project_sources, containers))
    objects, residuals = ecuc_objects(inspection, project_sources, containers)
    objects = prefix_sources(objects)
    sources = {"project/" + k: v for k, v in project_sources.items()}
    inventory = prefix_sources(inspection["sources"])
    app_names, log_names = [], []

    def load(path: Path, name: str, role: str) -> bytes:
        if path.is_symlink():
            raise ValueError("Additional inputs must not be symlinks")
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        if (
            len(data) > MAX_FILE
            or sum(map(len, sources.values())) + len(data) > MAX_TOTAL
        ):
            raise ValueError("Review input size limit exceeded")
        sources[name] = data
        inventory.append(
            {
                "file": name,
                "role": role,
                "sha256": sha(data),
                "bytes": len(data),
                "schema_location": "",
            }
        )
        return data

    for i, path in enumerate(applications):
        name = f"applications/{i:04d}.arxml"
        data = load(path, name, "application")
        app_objects, residual = application_objects(data, name)
        objects.extend(app_objects)
        residuals[name] = residual
        app_names.append(name)
    if len(objects) > 100000:
        raise ValueError("Review exceeds the 100000 object limit")
    modules = {
        m["path"]: m["definition"].rsplit("/", 1)[-1] for m in inspection["modules"]
    }
    integration = analyze(objects, modules, inspection["selected_modules"])
    by_path: dict[str, list[str]] = {}
    for obj in objects:
        by_path.setdefault(obj["path"], []).append(obj["id"])
    history = []
    for i, path in enumerate(logs):
        name = f"tool-logs/{i:04d}.log"
        raw = load(path, name, "tool-log").decode("utf-8-sig")
        rows = []
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            match = LOG_LINE.fullmatch(line)
            severity, code, object_path, message = (
                match.groups() if match else ("UNPARSED", "", "", line)
            )
            ids = by_path.get(object_path, [])
            rows.append(
                {
                    "line": line_number,
                    "severity": severity,
                    "code": code,
                    "message": message,
                    "object_path": object_path,
                    "object_ids": ids,
                    "association": "exact-path"
                    if len(ids) == 1
                    else "ambiguous"
                    if ids
                    else "unassessed",
                }
            )
        history.append({"file": name, "binding": "historical-unbound", "records": rows})
        log_names.append(name)
    gaps = [*prefix_sources(inspection["findings"]), *integration["findings"]]
    partial = bool(gaps) or communication["status"] != "resolved-in-scope"
    partial = partial or any(
        v == "unassessed"
        for k, v in integration["coverage"].items()
        if k in {"application", "task_bindings", "mode_rules"}
    )
    report = {
        "schema_version": VERSION,
        "status": "attention-required" if partial else "no-issues-in-scope",
        "scope": SCOPE,
        "inputs": {
            "project": "project/" + inspection["project"],
            "applications": app_names,
            "tool_logs": log_names,
        },
        "sources": sorted(inventory, key=lambda x: x["file"]),
        "selected_modules": inspection["selected_modules"],
        "objects": objects,
        "residuals": residuals,
        "communication": communication,
        "integration": integration,
        "historical_tool_logs": history,
        "summary": {
            "object_count": len(objects),
            "communication_paths": len(communication["paths"]),
            "partial_paths": sum(
                p["status"] == "partial" for p in communication["paths"]
            ),
            "applications": len(integration["applications"]),
            "task_bindings": len(integration["bindings"]),
            "mode_rules": len(integration["mode_rules"]),
            "structural_findings": len(gaps),
            "historical_log_records": sum(len(h["records"]) for h in history),
        },
    }
    return report, sources


def run_review(
    project: Path,
    output: Path,
    applications: list[Path] | None = None,
    logs: list[Path] | None = None,
) -> dict[str, Any]:
    check_output(output, project)
    report, sources = build(project, applications or [], logs or [])
    for name, data in sources.items():
        target = output / "snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "ecuc-review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "index.html").write_text(
        render("ECUC engineering review", report), encoding="utf-8"
    )
    return report


def read_verified(path: Path) -> dict[str, Any]:
    if path.name != "ecuc-review.json" or path.is_symlink():
        raise ValueError("Expected ecuc-review.json, not a symlink")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != VERSION:
        raise ValueError("Unsupported ECUC engineering review")
    inputs = report.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {
        "project",
        "applications",
        "tool_logs",
    }:
        raise ValueError("Invalid review inputs")
    if not isinstance(inputs["project"], str) or any(
        not isinstance(inputs[k], list)
        or any(not isinstance(v, str) for v in inputs[k])
        for k in ("applications", "tool_logs")
    ):
        raise ValueError("Invalid review input paths")
    snapshot = path.parent / "snapshot"
    if snapshot.is_symlink() or any(p.is_symlink() for p in path.parent.rglob("*")):
        raise ValueError("Review inventory must not contain symlinks")
    expected, sources = build(
        safe_file(snapshot, inputs["project"]),
        [safe_file(snapshot, x) for x in inputs["applications"]],
        [safe_file(snapshot, x) for x in inputs["tool_logs"]],
    )
    actual = {
        p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()
    }
    if actual != set(sources) or {p.name for p in path.parent.iterdir()} != {
        "ecuc-review.json",
        "index.html",
        "snapshot",
    }:
        raise ValueError("Review inventory differs")
    if canonical(report) != canonical(expected):
        raise ValueError("Saved review differs from replayed sources")
    if (path.parent / "index.html").read_text(encoding="utf-8") != render(
        "ECUC engineering review", expected
    ):
        raise ValueError("Review HTML differs")
    return report


def verify_review(path: Path) -> dict[str, Any]:
    report = read_verified(path)
    return {
        "status": "passed",
        "schema_version": VERSION,
        "review_status": report["status"],
        "report_sha256": sha(path.read_bytes()),
        "source_count": len(report["sources"]),
    }
