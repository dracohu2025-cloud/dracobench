from __future__ import annotations

import json
from pathlib import Path

from .models import Case, case_from_dict


def load_cases(path: Path | str) -> list[Case]:
    case_path = Path(path)
    cases: list[Case] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(case_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
            case = case_from_dict(data)
        except Exception as exc:
            raise ValueError(f"{case_path}:{line_number}: invalid case: {exc}") from exc

        if case.id in seen:
            raise ValueError(f"{case_path}:{line_number}: duplicate case id: {case.id}")
        seen.add(case.id)
        cases.append(case)

    return cases


def filter_cases(cases: list[Case], suites: list[str] | None = None, limit: int | None = None) -> list[Case]:
    filtered = cases
    if suites:
        allowed = set(suites)
        filtered = [case for case in filtered if case.suite in allowed]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered

