from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from .models import Case, ScoreResult


def score_response(case: Case, response_text: str) -> ScoreResult:
    scorers = {
        "exact": score_exact,
        "contains_any": score_contains_any,
        "regex": score_regex,
        "json_schema_lite": score_json_schema_lite,
        "text_rules": score_text_rules,
        "code_python_tests": score_code_python_tests,
    }
    scorer = scorers.get(case.scorer)
    if scorer is None:
        raise ValueError(f"unknown scorer: {case.scorer}")
    return scorer(case, response_text)


def normalize_text(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n。！？.!?,，`")


def score_exact(case: Case, response_text: str) -> ScoreResult:
    expected = str(case.expected["answer"])
    normalize = bool(case.expected.get("normalize", True))
    left = normalize_text(response_text) if normalize else response_text.strip()
    right = normalize_text(expected) if normalize else expected.strip()
    passed = left == right
    return ScoreResult(passed=passed, score=1.0 if passed else 0.0, details={"expected": expected, "actual": response_text})


def score_contains_any(case: Case, response_text: str) -> ScoreResult:
    answers = [str(answer) for answer in case.expected.get("answers", [])]
    normalized_response = normalize_text(response_text)
    matched = [answer for answer in answers if normalize_text(answer) in normalized_response]
    passed = bool(matched)
    return ScoreResult(passed=passed, score=1.0 if passed else 0.0, details={"matched": matched})


def score_regex(case: Case, response_text: str) -> ScoreResult:
    pattern = str(case.expected["pattern"])
    flags = 0
    flag_text = str(case.expected.get("flags", ""))
    if "i" in flag_text:
        flags |= re.IGNORECASE
    if "s" in flag_text:
        flags |= re.DOTALL
    matched = re.search(pattern, response_text, flags=flags) is not None
    return ScoreResult(passed=matched, score=1.0 if matched else 0.0, details={"pattern": pattern})


def score_text_rules(case: Case, response_text: str) -> ScoreResult:
    required = [str(item) for item in case.expected.get("required", [])]
    required_any = [[str(option) for option in group] for group in case.expected.get("required_any", [])]
    forbidden = [str(item) for item in case.expected.get("forbidden", [])]
    min_chars = case.expected.get("min_chars")
    max_chars = case.expected.get("max_chars")

    missing = [item for item in required if item not in response_text]
    missing_any = [group for group in required_any if not any(option in response_text for option in group)]
    present_forbidden = [item for item in forbidden if item in response_text]
    char_count = len(response_text.strip())

    length_ok = True
    if min_chars is not None and char_count < int(min_chars):
        length_ok = False
    if max_chars is not None and char_count > int(max_chars):
        length_ok = False

    # Length control is intentionally diagnostic-only for now. Exact character-count
    # compliance is noisy across models and should not dominate the core ability score.
    passed = not missing and not missing_any and not present_forbidden
    return ScoreResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        details={
            "missing": missing,
            "missing_any": missing_any,
            "present_forbidden": present_forbidden,
            "char_count": char_count,
            "length_ok": length_ok,
            "length_scored": False,
        },
    )


def score_json_schema_lite(case: Case, response_text: str) -> ScoreResult:
    try:
        value = parse_json_response(response_text)
    except ValueError as exc:
        return ScoreResult(passed=False, score=0.0, details={"error": str(exc)})

    errors = validate_json_schema_lite(value, case.expected["schema"])
    passed = not errors
    return ScoreResult(passed=passed, score=1.0 if passed else 0.0, details={"errors": errors, "value": value})


def parse_json_response(response_text: str) -> Any:
    text = response_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON object: {exc}") from exc
    raise ValueError("response does not contain a JSON object")


def validate_json_schema_lite(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {value!r}")

    if "pattern" in schema and isinstance(value, str) and re.search(str(schema["pattern"]), value) is None:
        errors.append(f"{path}: value does not match pattern {schema['pattern']!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in value:
                errors.append(f"{path}: missing required field {field_name!r}")

        properties = schema.get("properties", {})
        for field_name, field_value in value.items():
            if field_name in properties:
                errors.extend(validate_json_schema_lite(field_value, properties[field_name], f"{path}.{field_name}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {field_name!r}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(value) < int(min_items):
            errors.append(f"{path}: expected at least {min_items} items")
        if max_items is not None and len(value) > int(max_items):
            errors.append(f"{path}: expected at most {max_items} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_json_schema_lite(item, item_schema, f"{path}[{index}]"))

    return errors


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def score_code_python_tests(case: Case, response_text: str) -> ScoreResult:
    code = extract_python_code(response_text)
    tests = [str(item) for item in case.expected.get("tests", [])]
    timeout_seconds = int(case.expected.get("timeout_seconds", 3))

    with tempfile.TemporaryDirectory(prefix="dracobench-code-") as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "solution.py").write_text(code, encoding="utf-8")
        test_body = "\n".join(tests)
        (temp_path / "test_solution.py").write_text(
            "import solution\n\n" + textwrap.dedent(test_body) + "\n",
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [sys.executable, str(temp_path / "test_solution.py")],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ScoreResult(passed=False, score=0.0, details={"error": "timeout"})

    passed = completed.returncode == 0
    return ScoreResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        details={
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        },
    )


def extract_python_code(response_text: str) -> str:
    fenced = re.search(r"```(?:python|py)?\s*(.*?)```", response_text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return response_text.strip()
