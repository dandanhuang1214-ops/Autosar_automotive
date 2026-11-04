"""Web-host client for the local Workbench MCP evidence service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from automotive_workbench.mcp_service import VERSION
from automotive_workbench.model_client import ModelClient
from automotive_workbench.project_ai_workflow import CATALOG_VERSION, VERSION as PROPOSAL_VERSION, select_check


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


async def _call_project_tool(endpoint: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import Client

    async with Client(endpoint, mode="2026-07-28", read_timeout_seconds=120) as client:
        response = await client.call_tool(name, arguments)
    if response.is_error or not isinstance(response.structured_content, dict):
        raise ValueError(f"MCP project tool {name} rejected the request")
    return response.structured_content


def _project_tool(endpoint: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    validate_endpoint(endpoint)
    try:
        return asyncio.run(_call_project_tool(endpoint, name, arguments))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Workbench MCP project service is unavailable") from exc


def propose_project_via_mcp(endpoint: str, source: Path, requirement: str,
                            model: str, ollama_url: str,
                            client: ModelClient | None = None) -> dict[str, Any]:
    """Let MCP own project I/O while this Host owns the model selection."""
    if not source.is_absolute() or source.is_symlink():
        raise ValueError("Choose an existing absolute project JSON path")
    project_path = str(source.resolve())
    snapshot = _project_tool(endpoint, "project_check_catalog", {"project_path": project_path})
    if (snapshot.get("schema_version") != CATALOG_VERSION
            or snapshot.get("project_path") != project_path
            or not isinstance(snapshot.get("project_sha256"), str)
            or not isinstance(snapshot.get("input_sha256"), dict)
            or not isinstance(snapshot.get("available_checks"), list)):
        raise ValueError("MCP project check catalog is incompatible")
    selection = select_check(requirement, snapshot["available_checks"], model, ollama_url, client)
    proposal = _project_tool(endpoint, "create_project_candidate", {
        "project_path": project_path, "requirement": requirement,
        "selection": selection, "project_sha256": snapshot["project_sha256"],
        "input_sha256": snapshot["input_sha256"],
    })
    if (proposal.get("contract_version") != PROPOSAL_VERSION
            or proposal.get("status") != "draft_unassessed"
            or proposal.get("project", {}).get("sha256") != snapshot["project_sha256"]
            or proposal.get("selection", {}).get("acceptance_ids") != [selection["selected_id"]]):
        raise ValueError("MCP project candidate is incompatible")
    return proposal


def validate_project_via_mcp(endpoint: str, task_id: str) -> dict[str, Any]:
    result = _project_tool(endpoint, "validate_project_candidate", {"task_id": task_id})
    if (result.get("contract_version") != "ai-project-validation-0.1"
            or result.get("task_id") != task_id
            or result.get("status") not in {"passed", "failed", "blocked", "unassessed"}
            or result.get("verification_status") not in {"passed", "failed", "blocked"}
            or not isinstance(result.get("report_sha256"), str)):
        raise ValueError("MCP project validation is incompatible")
    return result
