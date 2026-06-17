from collections import Counter
from pathlib import Path
from unittest import TestCase

from dracobench.cases import load_cases
from dracobench.scorers import score_response


class ChallengeCaseSetTests(TestCase):
    def test_v02_challenge_has_expected_shape(self) -> None:
        cases = load_cases(Path("cases/v0.2/challenge.jsonl"))

        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case.id for case in cases}), 50)
        self.assertTrue(all(case.id.startswith("challenge-") for case in cases))

        suites = Counter(case.suite for case in cases)
        self.assertGreaterEqual(suites["coding"], 14)
        self.assertGreaterEqual(suites["debugging"], 14)
        self.assertGreaterEqual(suites["reasoning"], 7)
        self.assertGreaterEqual(suites["rag_long_context"], 7)
        self.assertGreaterEqual(suites["instruction_following"], 5)
        self.assertGreaterEqual(suites["chinese_writing"], 3)

    def test_v02_challenge_uses_known_scorers(self) -> None:
        for case in load_cases(Path("cases/v0.2/challenge.jsonl")):
            with self.subTest(case_id=case.id):
                try:
                    score_response(case, "")
                except ValueError as exc:
                    self.fail(str(exc))

    def test_v03_challenge_has_expected_shape(self) -> None:
        cases = load_cases(Path("cases/v0.3/challenge.jsonl"))

        self.assertEqual(len(cases), 100)
        self.assertEqual(len({case.id for case in cases}), 100)
        self.assertTrue(all(case.id.startswith("challenge-") for case in cases))

        suites = Counter(case.suite for case in cases)
        self.assertEqual(suites["coding"], 28)
        self.assertEqual(suites["debugging"], 19)
        self.assertEqual(suites["reasoning"], 25)
        self.assertEqual(suites["rag_long_context"], 18)
        self.assertEqual(suites["instruction_following"], 6)
        self.assertEqual(suites["chinese_writing"], 4)

    def test_v03_challenge_uses_known_scorers(self) -> None:
        for case in load_cases(Path("cases/v0.3/challenge.jsonl")):
            with self.subTest(case_id=case.id):
                try:
                    score_response(case, "")
                except ValueError as exc:
                    self.fail(str(exc))
