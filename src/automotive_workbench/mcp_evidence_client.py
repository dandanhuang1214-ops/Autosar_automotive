"""Web-host client for the local Workbench MCP evidence service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from automotive_workbench.mcp_service import VERSION


def validate_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.port is None or parsed.path != "/mcp" or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("MCP endpoint must be a local http://127.0.0.1:PORT/mcp URL")
    return value


async def _load(endpoint: str, report: Path, question: str) -> dict[str, Any]:
    from mcp import Client

    async with Client(endpoint, mode="2026-07-28", read_timeout_seconds=60) as client:
        response = await client.call_tool("project_evidence", {
            "report_path": str(report.resolve()), "question": question,
        })
    if response.is_error or not isinstance(response.structured_content, dict):
        raise ValueError("MCP service did not return structured project evidence")
    result = response.structured_content
    if (result.get("schema_version") != VERSION
            or result.get("report_path") != str(report.resolve())
            or result.get("question") != question.strip()
            or result.get("project_status") not in {"passed", "failed", "blocked", "unassessed"}
            or not isinstance(result.get("report_sha256"), str)
            or not isinstance(result.get("facts"), list)
            or not isinstance(result.get("boundary"), str)):
        raise ValueError("MCP service returned incompatible project evidence")
    return result


def load_project_evidence(endpoint: str, report: Path, question: str) -> dict[str, Any]:
    """Read evidence through MCP from the synchronous local web host."""
    validate_endpoint(endpoint)
    try:
        return asyncio.run(_load(endpoint, report, question))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Workbench MCP evidence service is unavailable") from exc
