from pathlib import Path
from unittest import TestCase

from dracobench.cases import load_cases


class CaseLoadingTests(TestCase):
    def test_load_smoke_cases(self) -> None:
        cases = load_cases(Path("cases/v0.1/smoke.jsonl"))

        self.assertGreaterEqual(len(cases), 7)
        self.assertEqual(len({case.id for case in cases}), len(cases))

