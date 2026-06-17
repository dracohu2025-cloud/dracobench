from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Case:
    id: str
    suite: str
    version: str
    prompt: str
    scorer: str
    expected: dict[str, Any]
    language: str = "zh"
    system: str | None = None
    tags: list[str] = field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None
    contamination_risk: str | None = None


@dataclass(frozen=True)
class ScoreResult:
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)


def case_from_dict(data: dict[str, Any]) -> Case:
    required = ["id", "suite", "version", "prompt", "scorer", "expected"]
    missing = [field_name for field_name in required if field_name not in data]
    if missing:
        raise ValueError(f"case is missing required fields: {', '.join(missing)}")

    return Case(
        id=str(data["id"]),
        suite=str(data["suite"]),
        version=str(data["version"]),
        language=str(data.get("language", "zh")),
        system=data.get("system"),
        prompt=str(data["prompt"]),
        scorer=str(data["scorer"]),
        expected=dict(data["expected"]),
        tags=list(data.get("tags", [])),
        temperature=data.get("temperature"),
        max_tokens=data.get("max_tokens"),
        contamination_risk=data.get("contamination_risk"),
    )

