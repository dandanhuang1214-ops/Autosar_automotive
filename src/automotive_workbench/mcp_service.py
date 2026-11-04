"""Optional MCP adapter for replay-verified Workbench project evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from automotive_workbench.project_ai_workflow import catalog, create_candidate, validate
from automotive_workbench.project_ecuc import verify as verify_project
from automotive_workbench.project_explanation import build_request

VERSION = "workbench-mcp-project-evidence-0.1"


def _report_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Report path must be an absolute path under the configured root")
    candidate = Path(value)
    if not candidate.is_absolute() or candidate.is_symlink():
        raise ValueError("Report path must be an absolute non-symlink path")
    resolved = candidate.resolve()
    if (not resolved.is_relative_to(root) or not resolved.is_file()
            or any(part.is_symlink() for part in (candidate, *candidate.parents)
                   if part.is_relative_to(root))):
        raise ValueError("Report path is outside the configured root or missing")
    return resolved


def _project_path(root: Path, value: str) -> Path:
    project_path = _report_path(root, value)
    project = json.loads(project_path.read_text(encoding="utf-8-sig"))
    inputs = project.get("inputs") if isinstance(project, dict) else None
    if not isinstance(inputs, dict):
        raise ValueError("Project inputs are invalid")
    for role in ("baseline", "candidate"):
        item = inputs.get(role)
        if not isinstance(item, dict) or not isinstance(item.get("project"), str):
            raise ValueError("Project inputs are invalid")
        _report_path(root, str(project_path.parent / item["project"]))
    return project_path


def build_server(root: Path, *, enable_project_actions: bool = False) -> Any:
    """Build a local project evidence service with opt-in project actions."""
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError("Install the optional mcp extra: pip install '.[mcp]'") from exc

    allowed_root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("MCP evidence root must be an existing non-symlink directory")
    server = MCPServer("automotive-workbench", version="0.1.0")
    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=False)
    project_action = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                     idempotent_hint=False, open_world_hint=False)

    @server.tool(annotations=read_only)
    def verify_project_report(report_path: str) -> dict[str, Any]:
        """Replay an ECUC project report and return its engineering status and hash."""
        report = _report_path(allowed_root, report_path)
        result = verify_project(report)
        return {"schema_version": "workbench-mcp-project-verification-0.1",
                "report_path": str(report), **result}

    @server.tool(annotations=read_only)
    def project_evidence(report_path: str, question: str) -> dict[str, Any]:
        """Return replay-verified project facts for a question; no model conclusion."""
        report = _report_path(allowed_root, report_path)
        request = build_request(report, question)
        return {"schema_version": VERSION, "report_path": str(report),
                "request_id": request["request_id"], "question": request["question"],
                "report_sha256": request["report_sha256"],
                "project_status": request["project_status"],
                "boundary": request["boundary"],
                "available_fact_count": len(request["facts"]),
                "facts": request["facts"][:16]}

    if enable_project_actions:
        @server.tool(annotations=read_only)
        def project_check_catalog(project_path: str) -> dict[str, Any]:
            """Read declared ECUC check IDs and bind them to source hashes for Host selection."""
            return catalog(_project_path(allowed_root, project_path))

        @server.tool(annotations=project_action)
        def create_project_candidate(project_path: str, requirement: str,
                                     selection: dict[str, Any], project_sha256: str,
                                     input_sha256: dict[str, dict[str, str]]) -> dict[str, Any]:
            """Write a draft project declaration from a Host-selected declared check."""
            return create_candidate(allowed_root, _project_path(allowed_root, project_path),
                                    requirement, selection, project_sha256, input_sha256)

        @server.tool(annotations=project_action)
        def validate_project_candidate(task_id: str) -> dict[str, Any]:
            """Run and replay-verify a previously saved candidate once after user confirmation."""
            if (not isinstance(task_id, str) or len(task_id) != 32
                    or any(c not in "0123456789abcdef" for c in task_id)):
                raise ValueError("Invalid AI project task ID")
            task = allowed_root / "project-tasks" / task_id
            if task.is_symlink() or (task / "proposal.json").is_symlink():
                raise ValueError("AI project task contains a symlink")
            proposal = json.loads((task / "proposal.json").read_text(encoding="utf-8"))
            _project_path(allowed_root, proposal["project"]["path"])
            return validate(allowed_root, task_id)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Workbench MCP project evidence service")
    parser.add_argument("--root", type=Path, required=True,
                        help="Only project reports inside this directory may be read")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--enable-project-actions", action="store_true",
                        help="Allow candidate declaration and validation under --root")
    args = parser.parse_args()
    server = build_server(args.root, enable_project_actions=args.enable_project_actions)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", host="127.0.0.1", port=args.port,
                   stateless_http=True, json_response=True)


if __name__ == "__main__":
    main()
