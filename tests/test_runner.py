from unittest import TestCase

from dracobench.models import Case
from dracobench.openrouter import OpenRouterResult
from dracobench.runner import run_one_case


class FakeClient:
    def chat_completion(self, payload):
        return OpenRouterResult(
            response={
                "id": "fake-response",
                "choices": [{"message": {"content": "42"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
            latency_ms=12,
        )


class RunnerTests(TestCase):
    def test_run_one_case_records_prompt_for_reports(self) -> None:
        case = Case(
            id="runner-001",
            suite="reasoning",
            version="0.1.0",
            prompt="只回答最终数字：40 + 2 = ?",
            scorer="exact",
            expected={"answer": "42"},
        )

        record = run_one_case(
            client=FakeClient(),
            case=case,
            model="fake/model",
            provider=None,
            temperature=0,
            max_tokens=128,
            seed=None,
        )

        self.assertEqual(record["prompt"], case.prompt)
        self.assertEqual(record["prompt_hash"], "02d32f4abf79c3122fa021836a32ac1beada1833a9e9c3fed3851e717f0b9582")
