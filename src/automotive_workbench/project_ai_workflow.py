"""Bounded AI selection of declared ECUC checks, followed by real project execution."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from automotive_workbench.can_io import BusConfig
from automotive_workbench.ecuc_project import read_project
from automotive_workbench.explanation_services import Endpoint
from automotive_workbench.model_client import ModelClient, OllamaModelClient
from automotive_workbench.project_ecuc import declaration, verify as verify_project
from automotive_workbench.project_workflow import run_project

VERSION = "ai-project-proposal-0.1"
CATALOG_VERSION = "ai-project-check-catalog-0.1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _project(path: Path) -> tuple[dict[str, Any], str, dict[str, dict[str, str]]]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("Choose an existing absolute project JSON path")
    raw = path.read_bytes()
    project = declaration(json.loads(raw.decode("utf-8-sig")))
    if project["schema_version"] != "workbench-project-0.6":
        raise ValueError("AI project generation currently supports static workbench-project-0.6")
    sources: dict[str, dict[str, str]] = {}
    for role in ("baseline", "candidate"):
        item = project["inputs"][role]
        if item["applications"] or item["tool_logs"]:
            raise ValueError("AI project generation requires a static ECUC project without extra inputs")
        dpa = (path.parent / item["project"]).resolve()
        if not dpa.is_file() or dpa.is_symlink():
            raise ValueError(f"Missing {role} ECUC project")
        _, content, _ = read_project(dpa)
        sources[role] = {name: _sha(data) for name, data in sorted(content.items())}
    return project, _sha(raw), sources


def _generated(source: dict[str, Any], source_path: Path, ids: list[str]) -> dict[str, Any]:
    project = json.loads(json.dumps(source))
    project["name"] = source["name"] + " | AI selected checks"
    project["comparison_key"] = source["comparison_key"] + "-ai-selected"
    project["requirements"] = [item for item in source["requirements"] if item["id"] in ids]
    for item in project["inputs"].values():
        item["project"] = str((source_path.parent / item["project"]).resolve())
    declaration(project)
    return project


def catalog(source_path: Path) -> dict[str, Any]:
    """Expose the versioned check list without making a model decision."""
    source, source_sha, input_sha = _project(source_path)
    return {"schema_version": CATALOG_VERSION, "project_path": str(source_path.resolve()),
            "project_sha256": source_sha, "input_sha256": input_sha,
            "available_checks": [{"id": item["id"], "text": item["text"]}
                                 for item in source["requirements"]]}


class SelectionError(ValueError):
    def __init__(self, message: str, response: Any, transport: list[dict[str, Any]]):
        super().__init__(message)
        self.response = response
        self.transport = transport


def select_check(requirement: str, checks: list[dict[str, str]], model: str,
                 ollama_url: str, client: ModelClient | None = None) -> dict[str, Any]:
    """Keep the model call in the Host; its output remains an unassessed selection."""
    if not isinstance(requirement, str) or not 1 <= len(requirement.strip()) <= 2000:
        raise ValueError("Requirement must contain 1..2000 characters")
    if not isinstance(checks, list) or not checks or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not isinstance(item.get("text"), str) for item in checks):
        raise ValueError("Project check catalog is invalid")
    allowed = {item["id"] for item in checks}
    model_client = client or OllamaModelClient(Endpoint(ollama_url, 90))
    response: Any = None
    try:
        identity = model_client.identity(model)
        version = model_client.service_version()
        response = model_client.complete({
            "model": model, "stream": False, "think": False, "keep_alive": "2m",
            "messages": [
                {"role": "system", "content": "从给定验收项里选择最相关的一项。只输出一个验收 ID，不能输出说明或新 ID。"},
                {"role": "user", "content": json.dumps({"requirement": requirement.strip(),
                                                       "available_checks": checks}, ensure_ascii=False)},
            ],
            "options": {"temperature": 0, "seed": 0, "num_ctx": 8192, "num_predict": 128},
        })
        message = response.get("message") if isinstance(response, dict) else None
        if (not isinstance(response, dict) or response.get("done") is not True
                or response.get("done_reason") != "stop" or response.get("model") != model
                or not isinstance(message, dict) or message.get("role") != "assistant"
                or message.get("tool_calls")
                or not isinstance(message.get("content"), str)
                or type(response.get("prompt_eval_count")) is not int
                or type(response.get("eval_count")) is not int
                or response["prompt_eval_count"] < 0 or response["eval_count"] < 0
                or response["prompt_eval_count"] + response["eval_count"] > 8192):
            raise ValueError("Incomplete or invalid model selection")
        selected_id = message["content"].strip()
        if selected_id not in allowed:
            raise ValueError("Model selected an unknown check or returned extra text")
        if model_client.identity(model) != identity:
            raise ValueError("Model identity changed during project selection")
    except (ValueError, TypeError, KeyError) as exc:
        raise SelectionError(str(exc), response, model_client.records) from exc
    return {"selected_id": selected_id, "response": response,
            "transport": model_client.records, "model": model,
            "digest": identity["digest"], "service_version": version}


def create_candidate(root: Path, source_path: Path, requirement: str,
                     selection: dict[str, Any], expected_project_sha: str,
                     expected_input_sha: dict[str, dict[str, str]],
                     task_id: str | None = None) -> dict[str, Any]:
    """Bind an AI selection to current inputs and write a draft declaration."""
    if not isinstance(requirement, str) or not 1 <= len(requirement.strip()) <= 2000:
        raise ValueError("Requirement must contain 1..2000 characters")
    source, source_sha, input_sha = _project(source_path)
    if source_sha != expected_project_sha or input_sha != expected_input_sha:
        raise ValueError("Project inputs changed after check catalog was read")
    checks = {item["id"]: item["text"] for item in source["requirements"]}
    selected_id = selection.get("selected_id")
    model = selection.get("model")
    response = selection.get("response")
    message = response.get("message") if isinstance(response, dict) else None
    if (not isinstance(selected_id, str) or selected_id not in checks
            or not isinstance(model, str) or not model
            or not isinstance(response, dict) or response.get("done") is not True
            or response.get("done_reason") != "stop" or response.get("model") != model
            or not isinstance(message, dict) or message.get("role") != "assistant"
            or message.get("tool_calls") or message.get("content") != selected_id
            or type(response.get("prompt_eval_count")) is not int
            or type(response.get("eval_count")) is not int
            or response["prompt_eval_count"] < 0 or response["eval_count"] < 0
            or response["prompt_eval_count"] + response["eval_count"] > 8192
            or not isinstance(selection.get("digest"), str)
            or re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", selection["digest"]) is None
            or not isinstance(selection.get("service_version"), str)
            or not isinstance(selection.get("transport"), list)):
        raise ValueError("Invalid model selection for project candidate")
    task_id = task_id or uuid.uuid4().hex
    tasks = root / "project-tasks"
    if tasks.is_symlink():
        raise ValueError("AI project task root must not be a symlink")
    task = tasks / task_id
    if task.exists():
        if any(task.iterdir()):
            raise ValueError("AI project task already exists")
    else:
        task.mkdir(parents=True, exist_ok=False)
    request = {"requirement": requirement.strip(),
               "available_checks": [{"id": item["id"], "text": item["text"]}
                                    for item in source["requirements"]],
               "project_path": str(source_path.resolve()), "project_sha256": source_sha,
               "model": model}
    generated = _generated(source, source_path, [selected_id])
    generated_path = task / "generated-project.json"
    generated_raw = _canonical(generated)
    generated_path.write_bytes(generated_raw)
    result = {"contract_version": VERSION, "id": task_id, "status": "draft_unassessed",
              "requirement": requirement.strip(), "project": {"path": str(source_path.resolve()),
              "sha256": source_sha, "input_sha256": input_sha},
              "selection": {"acceptance_ids": [selected_id], "rationale": checks[selected_id]},
              "generated_project": {"path": str(generated_path), "sha256": _sha(generated_raw)},
              "model": {"name": model, "digest": selection["digest"],
                        "service_version": selection["service_version"],
                        "input_tokens": response["prompt_eval_count"],
                        "output_tokens": response["eval_count"],
                        "response_sha256": _sha(_canonical(response))},
              "scope": "AI selected existing check IDs; the generated declaration is a draft until run-project executes"}
    (task / "proposal.json").write_bytes(_canonical(result))
    (task / "model-trace.json").write_bytes(_canonical({"status": "accepted_draft", "request": request,
                                               "response": response, "transport": selection["transport"]}))
    return result


def propose(root: Path, source_path: Path, requirement: str, model: str, ollama_url: str,
            client: ModelClient | None = None) -> dict[str, Any]:
    if not isinstance(requirement, str) or not 1 <= len(requirement.strip()) <= 2000:
        raise ValueError("Requirement must contain 1..2000 characters")
    if not source_path.is_absolute() or source_path.is_symlink():
        raise ValueError("Choose an existing absolute project JSON path")
    source_path = source_path.resolve()
    snapshot = catalog(source_path)
    task_id = uuid.uuid4().hex
    task = root / "project-tasks" / task_id
    task.mkdir(parents=True, exist_ok=False)
    request = {"requirement": requirement.strip(),
               "available_checks": snapshot["available_checks"],
               "project_path": str(source_path),
               "project_sha256": snapshot["project_sha256"], "model": model}
    try:
        selection = select_check(requirement, snapshot["available_checks"], model,
                                 ollama_url, client)
    except SelectionError as exc:
        (task / "model-trace.json").write_bytes(_canonical({"status": "rejected", "request": request,
                                                "response": exc.response, "transport": exc.transport,
                                                "error": str(exc)}))
        raise
    return create_candidate(root, source_path, requirement, selection,
                            snapshot["project_sha256"], snapshot["input_sha256"], task_id)


def validate(root: Path, task_id: str) -> dict[str, Any]:
    if not isinstance(task_id, str) or len(task_id) != 32 or any(c not in "0123456789abcdef" for c in task_id):
        raise ValueError("Invalid AI project task ID")
    tasks = root / "project-tasks"
    task = tasks / task_id
    if (tasks.is_symlink() or task.is_symlink()
            or any((task / name).is_symlink() for name in (
                "proposal.json", "model-trace.json", "generated-project.json", "validation"))):
        raise ValueError("AI project task contains a symlink")
    proposal = json.loads((task / "proposal.json").read_text(encoding="utf-8"))
    if proposal.get("contract_version") != VERSION or proposal.get("id") != task_id:
        raise ValueError("Invalid AI project proposal")
    source_path = Path(proposal["project"]["path"])
    source, source_sha, input_sha = _project(source_path)
    if source_sha != proposal["project"]["sha256"] or input_sha != proposal["project"]["input_sha256"]:
        raise ValueError("Project inputs changed after AI selection")
    ids = proposal["selection"]["acceptance_ids"]
    if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or not set(ids) <= {item["id"] for item in source["requirements"]}):
        raise ValueError("AI project selection changed")
    trace = json.loads((task / "model-trace.json").read_text(encoding="utf-8"))
    request = {"requirement": proposal["requirement"],
               "available_checks": [{"id": item["id"], "text": item["text"]} for item in source["requirements"]],
               "project_path": str(source_path), "project_sha256": source_sha,
               "model": proposal["model"]["name"]}
    if (trace.get("status") != "accepted_draft" or trace.get("request") != request
            or _sha(_canonical(trace.get("response"))) != proposal["model"]["response_sha256"]
            or trace["response"]["message"]["content"].strip() != ids[0]
            or len(ids) != 1):
        raise ValueError("AI selection differs from saved model response")
    expected = _canonical(_generated(source, source_path, ids))
    generated_path = task / "generated-project.json"
    if (_sha(generated_path.read_bytes()) != proposal["generated_project"]["sha256"]
            or generated_path.read_bytes() != expected):
        raise ValueError("Generated project differs from bound source and selection")
    output = task / "validation"
    if output.exists():
        raise ValueError("AI project task has already been executed")
    run_result = run_project(generated_path, output, BusConfig("virtual", "ai-project-" + task_id))
    report_path = output / "bundle/project-report.json"
    verification = verify_project(report_path)
    result = {"contract_version": "ai-project-validation-0.1", "task_id": task_id,
              "status": run_result["project_status"], "integrity_status": run_result["integrity_status"],
              "verification_status": verification["status"], "report": str(report_path),
              "report_sha256": _sha(report_path.read_bytes()),
              "selected_acceptance_ids": ids,
              "scope": "Workbench run-project result for AI selected checks; omitted checks remain unassessed"}
    (task / "validation-result.json").write_bytes(_canonical(result))
    return result
