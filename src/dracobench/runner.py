from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Case
from .openrouter import OpenRouterClient, OpenRouterError, extract_text
from .scorers import score_response

DEFAULT_SYSTEM_PROMPT = (
    "You are participating in DracoBench, a model evaluation suite. "
    "Follow the user instructions exactly. Prefer concise answers when possible."
)


def run_cases(
    cases: list[Case],
    model: str,
    output_path: Path | str,
    provider: dict[str, Any] | None = None,
    temperature: float = 0,
    max_tokens: int = 1024,
    seed: int | None = None,
    sleep_seconds: float = 0,
) -> list[dict[str, Any]]:
    client = OpenRouterClient()
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    with out_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            record = run_one_case(
                client=client,
                case=case,
                model=model,
                provider=provider,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
            )
            records.append(record)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            if sleep_seconds:
                time.sleep(sleep_seconds)

    return records


def run_one_case(
    client: OpenRouterClient,
    case: Case,
    model: str,
    provider: dict[str, Any] | None,
    temperature: float,
    max_tokens: int,
    seed: int | None,
) -> dict[str, Any]:
    effective_temperature = case.temperature if case.temperature is not None else temperature
    effective_max_tokens = case.max_tokens if case.max_tokens is not None else max_tokens
    messages = [
        {"role": "system", "content": case.system or DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": case.prompt},
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": effective_temperature,
        "max_tokens": effective_max_tokens,
        "stream": False,
    }
    if provider:
        payload["provider"] = provider
    if seed is not None:
        payload["seed"] = seed

    base_record: dict[str, Any] = {
        "case_id": case.id,
        "suite": case.suite,
        "case_version": case.version,
        "tags": case.tags,
        "scorer": case.scorer,
        "expected": case.expected,
        "model": model,
        "provider": provider,
        "prompt": case.prompt,
        "parameters": {
            "temperature": effective_temperature,
            "max_tokens": effective_max_tokens,
            "seed": seed,
        },
        "prompt_hash": hashlib.sha256(case.prompt.encode("utf-8")).hexdigest(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = client.chat_completion(payload)
        output = extract_text(result.response)
        score = score_response(case, output)
        return {
            **base_record,
            "latency_ms": result.latency_ms,
            "output": output,
            "usage": result.response.get("usage"),
            "response_id": result.response.get("id"),
            "finish_reason": _finish_reason(result.response),
            "score": {
                "passed": score.passed,
                "score": score.score,
                "details": score.details,
            },
            "error": None,
        }
    except OpenRouterError as exc:
        return {
            **base_record,
            "latency_ms": None,
            "output": "",
            "usage": None,
            "response_id": None,
            "finish_reason": None,
            "score": {"passed": False, "score": 0.0, "details": {}},
            "error": {
                "type": "openrouter_error",
                "status_code": exc.status_code,
                "message": str(exc),
                "body": exc.body,
            },
        }
    except Exception as exc:
        return {
            **base_record,
            "latency_ms": None,
            "output": "",
            "usage": None,
            "response_id": None,
            "finish_reason": None,
            "score": {"passed": False, "score": 0.0, "details": {}},
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def _finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    if not choices:
        return None
    return choices[0].get("finish_reason")
