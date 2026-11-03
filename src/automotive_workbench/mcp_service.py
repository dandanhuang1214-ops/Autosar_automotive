"""Optional MCP adapter for replay-verified Workbench project evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

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
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Report path is outside the configured root or missing")
    return resolved


def build_server(root: Path) -> Any:
    """Build a local read-only MCP service without changing the core package API."""
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

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Workbench MCP project evidence service")
    parser.add_argument("--root", type=Path, required=True,
                        help="Only project reports inside this directory may be read")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    server = build_server(args.root)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", host="127.0.0.1", port=args.port,
                   stateless_http=True, json_response=True)


if __name__ == "__main__":
    main()
