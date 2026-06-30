from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | str = ".env", override: bool = False) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and (override or key not in os.environ):
            os.environ[key] = value


def get_openrouter_api_key() -> str:
    load_dotenv(override=True)
    key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to .env or the shell environment.")
    return key


def get_openrouter_base_url() -> str:
    load_dotenv()
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


def get_openrouter_headers() -> dict[str, str]:
    load_dotenv()
    headers: dict[str, str] = {}
    referer = os.getenv("OPENROUTER_HTTP_REFERER")
    title = os.getenv("OPENROUTER_APP_TITLE", "dracobench")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-OpenRouter-Title"] = title
    return headers


def get_volcengine_api_key() -> str:
    load_dotenv(override=True)
    key = os.getenv("VOLCENGINE_API_KEY")
    if not key:
        raise RuntimeError("VOLCENGINE_API_KEY is not set. Add it to .env or the shell environment.")
    return key


def get_volcengine_base_url() -> str:
    load_dotenv()
    return os.getenv("VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
