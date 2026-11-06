"""Isolated streaming transport for direct AI chat."""
from __future__ import annotations

import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from automotive_workbench.explanation_services import (
    MAX_RESPONSE, Endpoint, NoRedirect, ServiceError, parse_json,
)
from automotive_workbench.model_client import OllamaModelClient
from automotive_workbench.project_explanation import canonical


class StreamingEndpoint(Endpoint):
    def __init__(self, url: str, timeout: float):
        super().__init__(url, timeout)
        self._stream_response: Any = None

    def cancel_stream(self) -> None:
        response = self._stream_response
        if response is not None:
            response.close()

    def stream_request(self, payload: dict[str, Any]):
        if payload.get("stream") is not True:
            raise ValueError("Streaming Ollama chat requires stream=true")
        record: dict[str, Any] = {"path": "/api/chat", "method": "POST", "payload": payload,
                                  "http_status": None, "raw": "", "error": None}
        self.records.append(record)
        request = Request(self.url + "/api/chat", data=canonical(payload).encode(),
                          headers={"Content-Type": "application/json"})
        total = 0
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=self.timeout) as response:
                self._stream_response = response
                record["http_status"] = response.status
                for line in response:
                    total += len(line)
                    if total > MAX_RESPONSE or len(line) > 100_000:
                        raise ValueError("response_too_large")
                    record["raw"] += line.decode("utf-8")
                    if line.strip():
                        yield parse_json(line.decode("utf-8"))
        except HTTPError as exc:
            record["http_status"] = exc.code
            record["error"] = f"http_{exc.code}"
        except (URLError, TimeoutError, socket.timeout, OSError, ValueError, UnicodeError) as exc:
            record["error"] = "service_unavailable:" + type(exc).__name__
        finally:
            self._stream_response = None
        if record["error"]:
            raise ServiceError(record["error"])


class StreamingChatClient(OllamaModelClient):
    def __init__(self, endpoint: StreamingEndpoint):
        super().__init__(endpoint)
        self._stream_endpoint = endpoint

    def stream(self, payload: dict[str, Any]):
        return self._stream_endpoint.stream_request(payload)

    def cancel_stream(self) -> None:
        self._stream_endpoint.cancel_stream()
