import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from dracobench.cli import default_html_report_path
from dracobench.report import (
    build_html_report,
    build_index_report,
    explain_failure,
    select_preferred_run_paths,
    summarize_run_file,
)


class ReportHtmlTests(TestCase):
    def test_build_html_report_renders_summary_and_failures(self) -> None:
        records = [
            {
                "case_id": "hard-knowledge-001",
                "suite": "knowledge",
                "model": "moonshotai/kimi-k2.7-code",
                "prompt": "谁提出了 Isolation Forest？",
                "scorer": "exact",
                "expected": {"answer": "Isolation Forest was proposed by Liu, Ting, and Zhou."},
                "started_at": "2026-06-16T00:00:00+00:00",
                "latency_ms": 1200,
                "usage": {
                    "cost": 0.001,
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "completion_tokens_details": {"reasoning_tokens": 15},
                },
                "score": {"passed": True, "score": 1.0, "details": {}},
                "output": "Isolation",
                "error": None,
            },
            {
                "case_id": "hard-debugging-001",
                "suite": "debugging",
                "model": "moonshotai/kimi-k2.7-code",
                "prompt": "下面代码为什么会失败？<show original prompt>",
                "scorer": "regex",
                "expected": {"pattern": "FIX:\\s*return x"},
                "started_at": "2026-06-16T00:00:02+00:00",
                "latency_ms": 2400,
                "usage": {
                    "cost": 0.002,
                    "prompt_tokens": 30,
                    "completion_tokens": 40,
                    "completion_tokens_details": {"reasoning_tokens": 35},
                },
                "score": {"passed": False, "score": 0.0, "details": {"reason": "<bad regex>"}},
                "output": "wrong answer",
                "error": None,
            },
        ]

        html = build_html_report(records, title="DracoBench Result")

        self.assertIn("DracoBench Result", html)
        self.assertIn("moonshotai/kimi-k2.7-code", html)
        self.assertIn("50.0%", html)
        self.assertIn("Total time", html)
        self.assertIn("4s", html)
        self.assertIn("$0.003000", html)
        self.assertIn("Reasoning tokens", html)
        self.assertIn("All Questions &amp; Answers", html)
        self.assertIn("href=\"#all-qa\"", html)
        self.assertIn("qa-hard-knowledge-001", html)
        self.assertIn("谁提出了 Isolation Forest？", html)
        self.assertIn("Standard Answer / Scoring Expectation", html)
        self.assertIn("Answer: Isolation Forest was proposed by Liu, Ting, and Zhou.", html)
        self.assertIn("Expected regex pattern:", html)
        self.assertIn("Failure Type", html)
        self.assertIn("Failure type:", html)
        self.assertIn("regex_miss", html)
        self.assertIn("hard-debugging-001", html)
        self.assertIn("Prompt", html)
        self.assertIn("下面代码为什么会失败？&lt;show original prompt&gt;", html)
        self.assertIn("Mistake Analysis", html)
        self.assertIn("&lt;bad regex&gt;", html)
        self.assertIn("data-suite=\"debugging\"", html)

    def test_explain_failure_describes_wrong_key_type_assumption(self) -> None:
        record = {
            "case_id": "challenge-coding-004",
            "suite": "coding",
            "prompt": "实现 LRU cache。ops 包含 \"put key value\" 和 \"get key\"。",
            "output": "key = int(parts[1])\nvalue = int(parts[2])",
            "finish_reason": "stop",
            "score": {
                "passed": False,
                "details": {
                    "stderr": "ValueError: invalid literal for int() with base 10: 'a'",
                },
            },
        }

        explanation = explain_failure(record)

        self.assertIn("key", explanation)
        self.assertIn("整数", explanation)
        self.assertIn("错误假设", explanation)

    def test_explain_failure_describes_length_empty_output(self) -> None:
        record = {
            "case_id": "challenge-rag-003",
            "suite": "rag_long_context",
            "finish_reason": "length",
            "output": "",
            "score": {"passed": False, "details": {}},
        }

        explanation = explain_failure(record)

        self.assertIn("输出预算", explanation)
        self.assertIn("空输出", explanation)

    def test_explain_failure_marks_duplicate_exact_answer(self) -> None:
        record = {
            "case_id": "challenge-reasoning-014",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "5", "normalize": True},
            "finish_reason": "stop",
            "output": "55",
            "score": {"passed": False, "details": {"expected": "5", "actual": "55"}},
        }

        explanation = explain_failure(record)

        self.assertIn("连续输出", explanation)
        self.assertIn("2 次", explanation)
        self.assertIn("不是核心推理错误", explanation)

    def test_explain_failure_marks_exact_format_violation(self) -> None:
        record = {
            "case_id": "challenge-reasoning-025",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "463", "normalize": True},
            "finish_reason": "stop",
            "output": "**463**",
            "score": {"passed": False, "details": {"expected": "463", "actual": "**463**"}},
        }

        explanation = explain_failure(record)

        self.assertIn("Markdown", explanation)
        self.assertIn("严格 exact scorer 判失败", explanation)

    def test_explain_failure_marks_exact_answer_mismatch(self) -> None:
        record = {
            "case_id": "challenge-reasoning-019",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "8", "normalize": True},
            "finish_reason": "stop",
            "output": "**10**",
            "score": {"passed": False, "details": {"expected": "8", "actual": "**10**"}},
        }

        explanation = explain_failure(record)

        self.assertIn("与标准答案 `8` 不一致", explanation)
        self.assertIn("总数 8", explanation)
        self.assertIn("最后一个字符不能是 C", explanation)

    def test_explain_failure_describes_rag_missing_evidence(self) -> None:
        record = {
            "case_id": "challenge-rag-009",
            "suite": "rag_long_context",
            "scorer": "text_rules",
            "finish_reason": "stop",
            "output": "不能。",
            "score": {
                "passed": False,
                "details": {
                    "missing": ["用户满意度"],
                    "missing_any": [["没有包含", "没有提供", "资料没有", "未包含"]],
                },
            },
        }

        explanation = explain_failure(record)

        self.assertIn("结论 `不能。` 方向正确", explanation)
        self.assertIn("没有说明依据", explanation)
        self.assertIn("用户满意度", explanation)

    def test_explain_failure_describes_code_boundary_bug(self) -> None:
        record = {
            "case_id": "challenge-coding-018",
            "suite": "coding",
            "scorer": "code_python_tests",
            "finish_reason": "stop",
            "output": "return result if result != '/' else result.rstrip('/')",
            "score": {
                "passed": False,
                "details": {"stderr": "AssertionError"},
            },
        }

        explanation = explain_failure(record)

        self.assertIn("根目录边界", explanation)
        self.assertIn("返回空字符串", explanation)

    def test_explain_failure_describes_version_sort_key_bug(self) -> None:
        record = {
            "case_id": "challenge-coding-027",
            "suite": "coding",
            "scorer": "code_python_tests",
            "finish_reason": "stop",
            "output": "return (major, minor, patch, label[0] if label else None)",
            "score": {
                "passed": False,
                "details": {"stderr": "TypeError: '<' not supported between instances of 'str' and 'NoneType'"},
            },
        }

        explanation = explain_failure(record)

        self.assertIn("字符串 label", explanation)
        self.assertIn("None", explanation)
        self.assertIn("同一类型的可比较 key", explanation)

    def test_explain_failure_describes_debugging_regex_format_miss(self) -> None:
        record = {
            "case_id": "challenge-debugging-003",
            "suite": "debugging",
            "scorer": "regex",
            "expected": {"pattern": r"FIX:\s*for\s+start\s+in\s+range\(0,\s*len\(items\),\s*page_size\)\s*:"},
            "finish_reason": "stop",
            "output": "修复方法是把 stop 改为 len(items)。\n\nFIX: range(0, len(items), page_size)",
            "score": {"passed": False, "details": {"pattern": r"FIX:\s*for\s+start\s+in\s+range\(0,\s*len\(items\),\s*page_size\)\s*:"}},
        }

        explanation = explain_failure(record)

        self.assertIn("FIX 行格式不完整", explanation)
        self.assertIn("不是分页逻辑没看懂", explanation)

    def test_explain_failure_describes_contains_any_wording_miss(self) -> None:
        record = {
            "case_id": "challenge-debugging-008",
            "suite": "debugging",
            "scorer": "contains_any",
            "expected": {"answers": ["删除 finally 中的 return None"]},
            "finish_reason": "stop",
            "output": "finally 里的 return 会覆盖 try 的返回值。\n\nFIX: 删除 `return None`",
            "score": {"passed": False, "details": {"matched": []}},
        }

        explanation = explain_failure(record)

        self.assertIn("最终短答案", explanation)
        self.assertIn("不是调试判断错误", explanation)

    def test_explain_failure_describes_indentation_error(self) -> None:
        record = {
            "case_id": "challenge-coding-016",
            "suite": "coding",
            "scorer": "code_python_tests",
            "finish_reason": "stop",
            "output": "if start <= current_end + 1:\ncurrent_end = max(current_end, end)",
            "score": {
                "passed": False,
                "details": {
                    "stderr": "IndentationError: expected an indented block after 'if' statement",
                },
            },
        }

        explanation = explain_failure(record)

        self.assertIn("缩进坏了", explanation)
        self.assertIn("IndentationError", explanation)

    def test_explain_failure_describes_top_k_tie_break_bug(self) -> None:
        record = {
            "case_id": "challenge-coding-021",
            "suite": "coding",
            "scorer": "code_python_tests",
            "finish_reason": "stop",
            "output": "first_occurrence = {item: idx for idx, item in enumerate(items)}",
            "score": {
                "passed": False,
                "details": {"stderr": "AssertionError"},
            },
        }

        explanation = explain_failure(record)

        self.assertIn("最后一次出现位置", explanation)
        self.assertIn("[y, z]", explanation)

    def test_explain_failure_describes_version_sort_flag_bug(self) -> None:
        record = {
            "case_id": "challenge-coding-027",
            "suite": "coding",
            "scorer": "code_python_tests",
            "finish_reason": "stop",
            "output": "return (numeric, 0 if label is None else 1, label)",
            "score": {
                "passed": False,
                "details": {"stderr": "AssertionError"},
            },
        }

        explanation = explain_failure(record)

        self.assertIn("排序方向写反", explanation)
        self.assertIn("正式版", explanation)

    def test_exact_answer_at_end_is_format_violation(self) -> None:
        record = {
            "case_id": "challenge-reasoning-002",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "D", "normalize": True},
            "finish_reason": "stop",
            "output": "推理过程很长\\n\\n**D**",
            "score": {"passed": False, "details": {"expected": "D", "actual": "推理过程很长\n\n**D**"}},
        }

        html = build_html_report([record], title="format")

        self.assertIn("format_violation", html)

    def test_explain_failure_describes_reasoning_derivation(self) -> None:
        record = {
            "case_id": "challenge-reasoning-017",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "3", "normalize": True},
            "finish_reason": "stop",
            "output": "2",
            "score": {"passed": False, "details": {"expected": "3", "actual": "2"}},
        }

        explanation = explain_failure(record)

        self.assertIn("第二层 `{b,c,g}`", explanation)
        self.assertIn("漏掉了", explanation)

    def test_explain_failure_describes_degenerate_output(self) -> None:
        record = {
            "case_id": "challenge-reasoning-015",
            "suite": "reasoning",
            "scorer": "exact",
            "expected": {"answer": "3", "normalize": True},
            "finish_reason": "length",
            "output": "</think></arg_value>" * 20,
            "score": {"passed": False, "details": {"expected": "3", "actual": "</think></arg_value>"}},
        }

        explanation = explain_failure(record)

        self.assertIn("生成阶段退化", explanation)
        self.assertIn("不是集合操作推理失败", explanation)

    def test_explain_failure_marks_duplicate_json_object(self) -> None:
        duplicated = (
            '{"status":"review","scores":{"coding":85,"debugging":80,"rag":75},"note":"评估中，待审核"}'
            '{"status":"review","scores":{"coding":85,"debugging":80,"rag":75},"note":"评估中，待审核"}'
        )
        record = {
            "case_id": "challenge-if-001",
            "suite": "instruction_following",
            "scorer": "json_schema_lite",
            "expected": {
                "schema": {
                    "type": "object",
                    "required": ["status", "scores", "note"],
                    "additionalProperties": False,
                    "properties": {
                        "status": {"type": "string", "const": "review"},
                        "scores": {
                            "type": "object",
                            "required": ["coding", "debugging", "rag"],
                            "additionalProperties": False,
                            "properties": {
                                "coding": {"type": "integer"},
                                "debugging": {"type": "integer"},
                                "rag": {"type": "integer"},
                            },
                        },
                        "note": {"type": "string"},
                    },
                }
            },
            "finish_reason": "stop",
            "output": duplicated,
            "score": {
                "passed": False,
                "details": {"error": "invalid JSON object: Extra data: line 1 column 84 (char 83)"},
            },
        }

        explanation = explain_failure(record)
        html = build_html_report([record], title="JSON failure")

        self.assertIn("连续输出了 2 个 JSON 对象", explanation)
        self.assertIn("每个对象单独看都符合 schema", explanation)
        self.assertIn("不是字段值本身错误", explanation)
        self.assertIn("duplicate_json_object", html)

    def test_default_html_report_path_uses_html_extension(self) -> None:
        path = default_html_report_path("moonshotai/kimi-k2.7-code")

        self.assertTrue(path.startswith("reports/"))
        self.assertTrue(path.endswith("-moonshotai-kimi-k2-7-code.html"))

    def test_build_index_report_links_model_to_detail_page(self) -> None:
        html = build_index_report(
            [
                {
                    "model": "deepseek/deepseek-v4-flash",
                    "run_name": "v0.2-challenge50-deepseek-deepseek-v4-flash-ability16384-rescored",
                    "run_href": "../runs/v0.2-challenge50-deepseek-deepseek-v4-flash-ability16384-rescored.jsonl",
                    "detail_href": "v0.2-challenge50-deepseek-deepseek-v4-flash-ability16384-rescored.html",
                    "case_count": 50,
                    "passed": 41,
                    "pass_rate": "82.0%",
                    "pass_rate_value": 0.82,
                    "avg_latency_ms": 8123,
                    "total_elapsed_ms": 123456,
                    "cost": 0.006722,
                    "prompt_tokens": 4719,
                    "completion_tokens": 22761,
                    "reasoning_tokens": 19746,
                    "finish_reasons": {"stop": 50},
                    "suite_summary": [{"suite": "coding", "passed": 13, "total": 14}],
                    "mode": "ability16384",
                    "temperature": 0,
                    "rescored": True,
                }
            ],
            title="DracoBench Index",
        )

        self.assertIn("DracoBench Index", html)
        self.assertIn("deepseek/deepseek-v4-flash", html)
        self.assertIn("Score Ranking", html)
        self.assertIn("ranking-chart", html)
        self.assertIn("chart-bar", html)
        self.assertIn("rank-pill", html)
        self.assertIn("v0.2-challenge50-deepseek-deepseek-v4-flash-ability16384-rescored.html", html)
        self.assertIn("41/50", html)
        self.assertIn("coding 13/14", html)
        self.assertIn("rescored", html)
        self.assertIn("Token Usage", html)
        self.assertIn("Total Time", html)
        self.assertIn("2m 03s", html)
        self.assertIn("Prompt = 输入题目与系统提示", html)
        self.assertIn("Prompt", html)
        self.assertIn("Completion", html)
        self.assertIn("Reasoning", html)
        self.assertIn("4719", html)
        self.assertIn("22761", html)
        self.assertIn("19746", html)

    def test_summarize_run_file_uses_site_absolute_links_for_vercel(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_dir = root / "runs"
            reports_dir = root / "reports"
            runs_dir.mkdir()
            reports_dir.mkdir()

            run_path = runs_dir / "v0.3-challenge100-z-ai-glm-5-2-ability16384.jsonl"
            report_path = reports_dir / "v0.3-challenge100-z-ai-glm-5-2-ability16384.html"
            record = {
                "case_id": "challenge-coding-001",
                "suite": "coding",
                "model": "z-ai/glm-5.2",
                "parameters": {"max_tokens": 16384, "temperature": 0},
                "latency_ms": 1000,
                "usage": {},
                "finish_reason": "stop",
                "score": {"passed": True},
            }
            run_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            report_path.write_text("<!doctype html>", encoding="utf-8")

            summary = summarize_run_file(run_path, index_path=reports_dir / "index.html")

        self.assertEqual(summary["run_href"], "/runs/v0.3-challenge100-z-ai-glm-5-2-ability16384.jsonl")
        self.assertEqual(summary["detail_href"], "/reports/v0.3-challenge100-z-ai-glm-5-2-ability16384.html")

    def test_select_preferred_run_paths_prefers_rescored_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            raw = base / "model-a.jsonl"
            rescored = base / "model-a-rescored.jsonl"
            other = base / "model-b.jsonl"
            raw.write_text("{}", encoding="utf-8")
            rescored.write_text("{}", encoding="utf-8")
            other.write_text("{}", encoding="utf-8")

            paths = select_preferred_run_paths([raw, rescored, other])

        self.assertEqual(paths, [rescored, other])
