from collections import Counter
from pathlib import Path
from unittest import TestCase

from dracobench.cases import load_cases
from dracobench.scorers import score_response


class HardCaseSetTests(TestCase):
    def test_v01_hard_has_expected_shape(self) -> None:
        cases = load_cases(Path("cases/v0.1/hard.jsonl"))

        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case.id for case in cases}), 50)
        self.assertTrue(all(case.id.startswith("hard-") for case in cases))

        suites = Counter(case.suite for case in cases)
        self.assertGreaterEqual(suites["knowledge"], 8)
        self.assertGreaterEqual(suites["reasoning"], 10)
        self.assertGreaterEqual(suites["coding"], 10)
        self.assertGreaterEqual(suites["debugging"], 8)
        self.assertGreaterEqual(suites["instruction_following"], 7)
        self.assertGreaterEqual(suites["chinese_writing"], 4)
        self.assertGreaterEqual(suites["rag_long_context"], 3)

    def test_v01_hard_uses_known_scorers(self) -> None:
        for case in load_cases(Path("cases/v0.1/hard.jsonl")):
            with self.subTest(case_id=case.id):
                try:
                    score_response(case, "")
                except ValueError as exc:
                    self.fail(str(exc))

