from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import get_openrouter_api_key, get_openrouter_base_url, get_openrouter_headers


@dataclass(frozen=True)
class OpenRouterResult:
    response: dict[str, Any]
    latency_ms: int


class OpenRouterError(RuntimeError):
    def __init__(self, status_code: int | None, message: str, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout_seconds: int = 120) -> None:
        self.api_key = api_key or get_openrouter_api_key()
        self.base_url = (base_url or get_openrouter_base_url()).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat_completion(self, payload: dict[str, Any]) -> OpenRouterResult:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **get_openrouter_headers(),
        }
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterError(exc.code, f"OpenRouter request failed with HTTP {exc.code}", error_body) from exc
        except urllib.error.URLError as exc:
            raise OpenRouterError(None, f"OpenRouter request failed: {exc.reason}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        return OpenRouterResult(response=json.loads(response_body), latency_ms=latency_ms)


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return ""

