"""Provider boundary for replayable model inference.

The current implementation deliberately exposes only the capabilities used by P30.
Structured output and native tool calling are explicit, tested capabilities; streaming
remains unsupported rather than inferred from a provider's marketing surface.
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


def _valid_messages(messages: Any) -> bool:
    return (
        isinstance(messages, list)
        and bool(messages)
        and all(
            isinstance(item, dict)
            and set(item) == {"role", "content"}
            and item["role"] in {"system", "user", "assistant"}
            and isinstance(item["content"], str)
            for item in messages
        )
    )


def _valid_tools(tools: Any) -> bool:
    if not isinstance(tools, list) or not tools:
        return False
    names: set[str] = set()
    for item in tools:
        if (
            not isinstance(item, dict)
            or set(item) != {"type", "function"}
            or item["type"] != "function"
            or not isinstance(item["function"], dict)
            or set(item["function"]) != {"name", "description", "parameters"}
        ):
            return False
        function = item["function"]
        name = function["name"]
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or not isinstance(function["description"], str)
            or not function["description"]
            or not isinstance(function["parameters"], dict)
        ):
            return False
        names.add(name)
    return True


@dataclass(frozen=True)
class ModelCapabilities:
    structured_output: bool
    tool_calling: bool
    streaming: bool
    identity_pinning: bool
    usage_metrics: bool


@dataclass(frozen=True)
class StructuredCompletion:
    """Provider-neutral structured completion consumed by AgentRunner."""

    content: str
    input_tokens: int
    output_tokens: int
    raw: Any


@dataclass(frozen=True)
class ToolCompletion:
    """One provider-native function call with measured token usage."""

    name: str
    arguments: dict[str, Any]
    content: str
    input_tokens: int
    output_tokens: int
    raw: Any


class ModelClient(Protocol):
    """Small provider-neutral contract needed by the evidence explanation path."""

    url: str
    records: list[dict[str, Any]]
    capabilities: ModelCapabilities

    def service_version(self) -> str: ...

    def identity(self, name: str) -> dict[str, Any]: ...

    def complete(self, payload: dict[str, Any]) -> Any: ...

    def usage(self, response: Any) -> dict[str, Any]: ...

    def complete_structured(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_output_tokens: int,
        context_window: int,
    ) -> StructuredCompletion: ...

    def complete_tool_call(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        context_window: int,
    ) -> ToolCompletion: ...


class OllamaModelClient:
    """Replay-compatible Ollama adapter over the existing bounded transport."""

    capabilities = ModelCapabilities(
        structured_output=True,
        tool_calling=True,
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
        version: str = value["version"]
        return version

    def identity(self, name: str) -> dict[str, Any]:
        return model_identity(self._endpoint, name)

    def complete(self, payload: dict[str, Any]) -> Any:
        return self._endpoint.request("/api/chat", payload)

    def usage(self, response: Any) -> dict[str, Any]:
        if not isinstance(response, dict):
            return {}
        return {field: response[field] for field in OLLAMA_METRIC_FIELDS if field in response}

    def complete_structured(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_output_tokens: int,
        context_window: int,
    ) -> StructuredCompletion:
        """Run one bounded JSON-schema completion without provider tool execution."""
        if (
            not isinstance(model, str)
            or not model
            or not _valid_messages(messages)
            or not isinstance(schema, dict)
            or type(max_output_tokens) is not int
            or not 1 <= max_output_tokens <= 4096
            or type(context_window) is not int
            or not 512 <= context_window <= 32768
        ):
            raise ValueError("Invalid structured completion request")
        response = self.complete(
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "think": False,
                "format": schema,
                "options": {
                    "temperature": 0,
                    "seed": 0,
                    "num_ctx": context_window,
                    "num_predict": max_output_tokens,
                },
                "keep_alive": "2m",
            }
        )
        if (
            not isinstance(response, dict)
            or response.get("done") is not True
            or response.get("done_reason") != "stop"
            or response.get("model") != model
            or not isinstance(response.get("message"), dict)
            or response["message"].get("role") != "assistant"
            or response["message"].get("tool_calls")
            or not isinstance(response["message"].get("content"), str)
        ):
            raise ValueError("incomplete_or_invalid_model_response")
        input_tokens = response.get("prompt_eval_count")
        output_tokens = response.get("eval_count")
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
            or input_tokens + output_tokens > context_window
        ):
            raise ValueError("invalid_or_exceeded_context_budget")
        return StructuredCompletion(
            content=response["message"]["content"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=response,
        )

    def complete_tool_call(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        context_window: int,
    ) -> ToolCompletion:
        """Run one bounded provider-native function selection."""
        if (
            not isinstance(model, str)
            or not model
            or not _valid_messages(messages)
            or not _valid_tools(tools)
            or type(max_output_tokens) is not int
            or not 1 <= max_output_tokens <= 4096
            or type(context_window) is not int
            or not 512 <= context_window <= 32768
        ):
            raise ValueError("Invalid tool completion request")
        response = self.complete(
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                    "seed": 0,
                    "num_ctx": context_window,
                    "num_predict": max_output_tokens,
                },
                "keep_alive": "2m",
            }
        )
        message = response.get("message") if isinstance(response, dict) else None
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if (
            not isinstance(response, dict)
            or response.get("done") is not True
            or response.get("done_reason") != "stop"
            or response.get("model") != model
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or not isinstance(calls, list)
            or len(calls) != 1
            or not isinstance(calls[0], dict)
            or not isinstance(calls[0].get("function"), dict)
        ):
            raise ValueError("incomplete_or_invalid_tool_response")
        function = calls[0]["function"]
        if (
            set(function) not in (
                {"name", "arguments"},
                {"index", "name", "arguments"},
            )
            or ("index" in function and function["index"] != 0)
            or not isinstance(function["name"], str)
            or not function["name"]
            or not isinstance(function["arguments"], dict)
        ):
            raise ValueError("invalid_tool_call")
        input_tokens = response.get("prompt_eval_count")
        output_tokens = response.get("eval_count")
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
            or input_tokens + output_tokens > context_window
        ):
            raise ValueError("invalid_or_exceeded_context_budget")
        return ToolCompletion(
            name=function["name"],
            arguments=function["arguments"],
            content=message["content"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=response,
        )
