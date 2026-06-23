from unittest import TestCase

from dracobench.volcengine import _to_responses_payload, extract_text


class VolcengineArkTests(TestCase):
    def test_to_responses_payload_moves_system_to_instructions(self) -> None:
        payload = _to_responses_payload(
            {
                "model": "doubao-seed-2-1-pro-260628",
                "messages": [
                    {"role": "system", "content": "Follow exactly."},
                    {"role": "user", "content": "只输出答案"},
                ],
                "temperature": 0,
                "max_tokens": 16384,
                "stream": False,
            }
        )

        self.assertEqual(payload["model"], "doubao-seed-2-1-pro-260628")
        self.assertEqual(payload["instructions"], "Follow exactly.")
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_output_tokens"], 16384)
        self.assertFalse(payload["stream"])
        self.assertEqual(
            payload["input"],
            [{"role": "user", "content": [{"type": "input_text", "text": "只输出答案"}]}],
        )

    def test_extract_text_reads_responses_output_content(self) -> None:
        text = extract_text(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "第一段"},
                            {"type": "output_text", "text": "第二段"},
                        ],
                    }
                ]
            }
        )

        self.assertEqual(text, "第一段\n第二段")

    def test_extract_text_prefers_output_text(self) -> None:
        text = extract_text({"output_text": "直接文本", "output": []})

        self.assertEqual(text, "直接文本")
