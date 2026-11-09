"""Bounded DeepSeek Chat Completions transport for direct AI platform chat."""
from __future__ import annotations

import json
import socket
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from automotive_workbench.explanation_services import MAX_RESPONSE, NoRedirect, ServiceError

URL = "https://api.deepseek.com/chat/completions"
MODELS = ("deepseek-flash", "deepseek-v4-pro")


class DeepSeekChatClient:
    def __init__(self, api_key: str, timeout: float = 120):
        if not api_key or api_key != api_key.strip() or "\r" in api_key or "\n" in api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        self._api_key = api_key
        self._timeout = timeout
        self._response: Any = None
        self.records: list[dict[str, Any]] = []

    def _request(self, payload: dict[str, Any]) -> Request:
        if payload.get("model") not in MODELS:
            raise ValueError("Unsupported DeepSeek model")
        body: dict[str, Any] = {
            "model": payload["model"], "messages": payload["messages"],
            "thinking": {"type": "disabled"}, "max_tokens": 2048,
            "stream": payload["stream"],
        }
        if payload["stream"]:
            body["stream_options"] = {"include_usage": True}
        self.records.append({"path": "/chat/completions", "method": "POST",
                             "payload": body, "http_status": None, "error": None})
        return Request(URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                       headers={"Content-Type": "application/json",
                                "Authorization": "Bearer " + self._api_key})

    def _open(self, request: Request):
        # Keep redirects disabled so a bearer token never follows a redirected URL.
        return build_opener(ProxyHandler(), NoRedirect()).open(request, timeout=self._timeout)

    @staticmethod
    def _choice(value: Any) -> dict[str, Any]:
        if (not isinstance(value, dict) or not isinstance(value.get("choices"), list)
                or len(value["choices"]) != 1 or not isinstance(value["choices"][0], dict)):
            raise ServiceError("invalid_deepseek_response")
        return value["choices"][0]

    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._request({**payload, "stream": False})
        record = self.records[-1]
        try:
            with self._open(request) as response:
                record["http_status"] = response.status
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ServiceError("response_too_large")
            value = json.loads(raw)
            choice = self._choice(value)
            message = choice.get("message")
            if (not isinstance(message, dict) or message.get("role") != "assistant"
                    or not isinstance(message.get("content"), str)):
                raise ServiceError("invalid_deepseek_response")
            usage = value.get("usage") if isinstance(value, dict) else None
            usage = usage if isinstance(usage, dict) else {}
            record["response_id"] = value.get("id")
            return {"done": True, "done_reason": choice.get("finish_reason"),
                    "model": payload["model"], "reported_model": value.get("model"),
                    "message": {"role": "assistant", "content": message["content"]},
                    "prompt_eval_count": usage.get("prompt_tokens"),
                    "eval_count": usage.get("completion_tokens"),
                    "response_id": value.get("id")}
        except HTTPError as exc:
            record["http_status"] = exc.code
            record["error"] = f"deepseek_http_{exc.code}"
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            record["error"] = "deepseek_unavailable:" + type(exc).__name__
        except ServiceError as exc:
            record["error"] = str(exc)
        except (ValueError, UnicodeError) as exc:
            record["error"] = "invalid_deepseek_response:" + type(exc).__name__
        if record["error"]:
            raise ServiceError(record["error"])
        raise ServiceError("invalid_deepseek_response")

    def stream(self, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
        request = self._request({**payload, "stream": True})
        record = self.records[-1]
        finish: str | None = None
        usage: dict[str, Any] = {}
        response_id: str | None = None
        reported_model: str | None = None
        done = False
        total = 0
        try:
            with self._open(request) as response:
                self._response = response
                record["http_status"] = response.status
                for line in response:
                    total += len(line)
                    if total > MAX_RESPONSE or len(line) > 100_000:
                        raise ServiceError("response_too_large")
                    if not line.startswith(b"data: "):
                        continue
                    data = line[6:].strip()
                    if data == b"[DONE]":
                        done = True
                        break
                    value = json.loads(data)
                    if (isinstance(value, dict) and value.get("choices") == []
                            and isinstance(value.get("usage"), dict)):
                        usage = value["usage"]
                        continue
                    choice = self._choice(value)
                    if value.get("model") is not None:
                        reported_model = value["model"]
                    if value.get("id") is not None:
                        response_id = value["id"]
                    delta = choice.get("delta")
                    if not isinstance(delta, dict) or not isinstance(delta.get("content", ""), str):
                        raise ServiceError("invalid_deepseek_stream")
                    if choice.get("finish_reason") is not None:
                        finish = choice["finish_reason"]
                    if isinstance(value.get("usage"), dict):
                        usage = value["usage"]
                    if delta.get("content"):
                        yield {"model": payload["model"], "message": {
                            "role": "assistant", "content": delta["content"]}, "done": False}
            if not done or finish is None:
                raise ServiceError("incomplete_deepseek_stream")
            record["response_id"] = response_id
            yield {"model": payload["model"], "reported_model": reported_model,
                   "response_id": response_id, "message": {"role": "assistant", "content": ""},
                   "done": True, "done_reason": finish,
                   "prompt_eval_count": usage.get("prompt_tokens"),
                   "eval_count": usage.get("completion_tokens")}
        except HTTPError as exc:
            record["http_status"] = exc.code
            record["error"] = f"deepseek_http_{exc.code}"
            raise ServiceError(record["error"]) from None
        except ServiceError as exc:
            record["error"] = str(exc)
            raise
        except (URLError, TimeoutError, socket.timeout, OSError, ValueError, UnicodeError) as exc:
            record["error"] = "deepseek_unavailable:" + type(exc).__name__
            raise ServiceError(record["error"]) from None
        finally:
            self._response = None

    def cancel_stream(self) -> None:
        if self._response is not None:
            self._response.close()
