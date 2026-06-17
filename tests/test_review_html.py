from unittest import TestCase

from dracobench.models import Case
from dracobench.review import build_review_html


class ReviewHtmlTests(TestCase):
    def test_build_review_html_escapes_and_renders_cases(self) -> None:
        cases = [
            Case(
                id="hard-if-001",
                suite="instruction_following",
                version="0.1.0",
                prompt="返回 <json> & 不要解释",
                scorer="text_rules",
                expected={"required": ["json"]},
                tags=["format", "hard"],
            )
        ]

        html = build_review_html(cases, title="DracoBench v0.1-hard")

        self.assertIn("DracoBench v0.1-hard", html)
        self.assertIn("hard-if-001", html)
        self.assertIn("instruction_following", html)
        self.assertIn("返回 &lt;json&gt; &amp; 不要解释", html)
        self.assertIn("data-suite=\"instruction_following\"", html)
