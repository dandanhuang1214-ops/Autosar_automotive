"""Provider boundary for replayable model inference.

The current implementation deliberately exposes only the capabilities used by P30.
Agent tool calling and streaming must be added as explicit, tested capabilities rather
than inferred from a provider's marketing surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from automotive_workbench.explanation_services import ServiceEndpoint, ServiceError, model_identity

OLLAMA_METRIC_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "eval_count",
    "eval_duration",
)


@dataclass(frozen=True)
class ModelCapabilities:
    structured_output: bool
    tool_calling: bool
    streaming: bool
    identity_pinning: bool
    usage_metrics: bool


class ModelClient(Protocol):
    """Small provider-neutral contract needed by the evidence explanation path."""

    url: str
    records: list[dict[str, Any]]
    capabilities: ModelCapabilities

    def service_version(self) -> str: ...

    def identity(self, name: str) -> dict: ...

    def complete(self, payload: dict) -> Any: ...

    def usage(self, response: Any) -> dict[str, Any]: ...


class OllamaModelClient:
    """Replay-compatible Ollama adapter over the existing bounded transport."""

    capabilities = ModelCapabilities(
        structured_output=True,
        tool_calling=False,
        streaming=False,
        identity_pinning=True,
        usage_metrics=True,
    )

    def __init__(self, endpoint: ServiceEndpoint):
        self._endpoint = endpoint

    @property
    def url(self) -> str:
        return self._endpoint.url

    @property
    def records(self) -> list[dict[str, Any]]:
        return self._endpoint.records

    def service_version(self) -> str:
        value = self._endpoint.request("/api/version")
        if not isinstance(value, dict) or not isinstance(value.get("version"), str) or not value["version"]:
            raise ServiceError("missing_service_version")
        return value["version"]

    def identity(self, name: str) -> dict:
        return model_identity(self._endpoint, name)

    def complete(self, payload: dict) -> Any:
        return self._endpoint.request("/api/chat", payload)

    def usage(self, response: Any) -> dict[str, Any]:
        if not isinstance(response, dict):
            return {}
        return {field: response[field] for field in OLLAMA_METRIC_FIELDS if field in response}
