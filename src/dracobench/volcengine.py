from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import get_volcengine_api_key, get_volcengine_base_url


@dataclass(frozen=True)
class VolcengineArkResult:
    response: dict[str, Any]
    latency_ms: int


class VolcengineArkError(RuntimeError):
    def __init__(self, status_code: int | None, message: str, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class VolcengineArkClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout_seconds: int = 420) -> None:
        self.api_key = api_key or get_volcengine_api_key()
        self.base_url = (base_url or get_volcengine_base_url()).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat_completion(self, payload: dict[str, Any]) -> VolcengineArkResult:
        request_payload = _to_responses_payload(payload)
        body = json.dumps(request_payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/responses",
            data=body,
            headers=headers,
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise VolcengineArkError(exc.code, f"Volcengine Ark request failed with HTTP {exc.code}", error_body) from exc
        except urllib.error.URLError as exc:
            raise VolcengineArkError(None, f"Volcengine Ark request failed: {exc.reason}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_response = json.loads(response_body)
        return VolcengineArkResult(response=_normalize_response(raw_response), latency_ms=latency_ms)


def _to_responses_payload(payload: dict[str, Any]) -> dict[str, Any]:
    instructions: list[str] = []
    input_items: list[dict[str, Any]] = []
    for message in payload.get("messages") or []:
        role = str(message.get("role") or "user")
        text = _message_text(message.get("content"))
        if not text:
            continue
        if role == "system":
            instructions.append(text)
            continue
        input_items.append(
            {
                "role": role,
                "content": [{"type": "input_text", "text": text}],
            }
        )

    request_payload: dict[str, Any] = {
        "model": payload["model"],
        "input": input_items,
    }
    if instructions:
        request_payload["instructions"] = "\n\n".join(instructions)
    if "temperature" in payload:
        request_payload["temperature"] = payload["temperature"]
    if payload.get("max_tokens") is not None:
        request_payload["max_output_tokens"] = payload["max_tokens"]
    if payload.get("stream") is not None:
        request_payload["stream"] = bool(payload["stream"])
    return request_payload


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content) if content is not None else ""


def _normalize_response(response: dict[str, Any]) -> dict[str, Any]:
    output_text = extract_text(response)
    return {
        "id": response.get("id"),
        "choices": [
            {
                "message": {"content": output_text},
                "finish_reason": _finish_reason(response),
            }
        ],
        "usage": _normalize_usage(response.get("usage") or {}),
        "status": response.get("status"),
    }


def extract_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, list):
            parts.extend(_content_texts(content))
        elif item.get("type") in {"output_text", "text"}:
            parts.append(str(item.get("text", "")))
    return "\n".join(part for part in parts if part)


def _content_texts(content: list[Any]) -> list[str]:
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"output_text", "text"}:
            parts.append(str(item.get("text", "")))
    return parts


def _finish_reason(response: dict[str, Any]) -> str | None:
    status = response.get("status")
    if status == "completed":
        return "stop"
    if isinstance(status, str):
        return status
    return None


def _normalize_usage(usage: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    reasoning_tokens = _reasoning_tokens(usage)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
        "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }


def _reasoning_tokens(usage: dict[str, Any]) -> int:
    for field_name in ("completion_tokens_details", "output_tokens_details"):
        details = usage.get(field_name) or {}
        if isinstance(details, dict):
            value = details.get("reasoning_tokens")
            if value is not None:
                return int(value)
    return 0
