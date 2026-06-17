from unittest import TestCase

from dracobench.models import Case
from dracobench.scorers import score_response


def make_case(scorer: str, expected: dict) -> Case:
    return Case(
        id="test",
        suite="unit",
        version="0.1.0",
        prompt="",
        scorer=scorer,
        expected=expected,
    )


class ScorerTests(TestCase):
    def test_exact_normalized(self) -> None:
        case = make_case("exact", {"answer": "42"})
        result = score_response(case, " 42。 ")
        self.assertTrue(result.passed)

    def test_contains_any(self) -> None:
        case = make_case("contains_any", {"answers": ["俄罗斯", "Russia"]})
        result = score_response(case, "答案是俄罗斯。")
        self.assertTrue(result.passed)

    def test_regex(self) -> None:
        case = make_case("regex", {"pattern": "FIX:\\s*for", "flags": "i"})
        result = score_response(case, "FIX: for i in range(len(items)):")
        self.assertTrue(result.passed)

    def test_text_rules(self) -> None:
        case = make_case("text_rules", {"required": ["模型评测"], "forbidden": ["遥遥领先"], "max_chars": 20})
        result = score_response(case, "模型评测要可复现")
        self.assertTrue(result.passed)

    def test_text_rules_records_but_does_not_score_length(self) -> None:
        case = make_case("text_rules", {"required": ["模型评测"], "max_chars": 4})
        result = score_response(case, "模型评测要可复现")
        self.assertTrue(result.passed)
        self.assertFalse(result.details["length_ok"])
        self.assertFalse(result.details["length_scored"])

    def test_text_rules_required_any(self) -> None:
        case = make_case(
            "text_rules",
            {"required": ["人工抽检"], "required_any": [["默认使用", "默认判分"]], "max_chars": 20},
        )
        result = score_response(case, "默认判分需人工抽检")
        self.assertTrue(result.passed)

    def test_json_schema_lite(self) -> None:
        case = make_case(
            "json_schema_lite",
            {
                "schema": {
                    "type": "object",
                    "required": ["title"],
                    "additionalProperties": False,
                    "properties": {"title": {"type": "string", "const": "DracoBench"}},
                }
            },
        )
        result = score_response(case, '{"title":"DracoBench"}')
        self.assertTrue(result.passed)

    def test_code_python_tests(self) -> None:
        case = make_case("code_python_tests", {"tests": ["assert solution.solve([2, 2, 1]) == 1"], "timeout_seconds": 3})
        result = score_response(case, "def solve(nums):\n    answer = 0\n    for num in nums:\n        answer ^= num\n    return answer")
        self.assertTrue(result.passed)
