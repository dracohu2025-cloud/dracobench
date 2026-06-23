from __future__ import annotations

import html
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .scorers import validate_json_schema_lite


def write_markdown_report(records: list[dict[str, Any]], path: Path | str) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(records)
    passed = sum(1 for record in records if record.get("score", {}).get("passed"))
    errored = sum(1 for record in records if record.get("error"))
    avg_latency = _avg([record.get("latency_ms") for record in records if record.get("latency_ms") is not None])
    usage_summary = _usage_summary(records)

    lines = [
        "# DracoBench Report",
        "",
        "## Summary",
        "",
        f"- Cases: {total}",
        f"- Passed: {passed}",
        f"- Pass rate: {_percent(passed, total)}",
        f"- Errors: {errored}",
        f"- Avg latency: {avg_latency:.0f} ms" if avg_latency is not None else "- Avg latency: n/a",
        f"- Total cost: ${usage_summary['cost']:.6f}",
        f"- Prompt tokens: {usage_summary['prompt_tokens']}",
        f"- Completion tokens: {usage_summary['completion_tokens']}",
        f"- Reasoning tokens: {usage_summary['reasoning_tokens']}",
        "",
        "## By Suite",
        "",
        "| Suite | Cases | Passed | Pass rate | Avg latency | Cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for suite, suite_records in sorted(_group_by_suite(records).items()):
        suite_total = len(suite_records)
        suite_passed = sum(1 for record in suite_records if record.get("score", {}).get("passed"))
        suite_latency = _avg(
            [record.get("latency_ms") for record in suite_records if record.get("latency_ms") is not None]
        )
        suite_usage = _usage_summary(suite_records)
        latency_text = f"{suite_latency:.0f} ms" if suite_latency is not None else "n/a"
        lines.append(
            f"| `{suite}` | {suite_total} | {suite_passed} | {_percent(suite_passed, suite_total)} | "
            f"{latency_text} | ${suite_usage['cost']:.6f} |"
        )

    failures = [record for record in records if not record.get("score", {}).get("passed") or record.get("error")]
    if failures:
        lines.extend(["", "## Failure Examples", ""])
        for record in failures[:5]:
            lines.extend(
                [
                    f"### {record.get('case_id')}",
                    "",
                    f"- Suite: `{record.get('suite')}`",
                    f"- Error: `{record.get('error')}`" if record.get("error") else f"- Score details: `{record.get('score', {}).get('details')}`",
                    "",
                    "Output:",
                    "",
                    "```text",
                    str(record.get("output", "")).strip()[:1200],
                    "```",
                    "",
                ]
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(records: list[dict[str, Any]], path: Path | str, title: str = "DracoBench Report") -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_html_report(records, title=title), encoding="utf-8")


def write_index_report(run_paths: list[Path | str], path: Path | str, title: str = "DracoBench Results Index") -> None:
    index_path = Path(path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    selected_paths = select_preferred_run_paths([Path(run_path) for run_path in run_paths])
    summaries = [summarize_run_file(run_path, index_path=index_path) for run_path in selected_paths]
    index_path.write_text(build_index_report(summaries, title=title), encoding="utf-8")


def build_html_report(records: list[dict[str, Any]], title: str = "DracoBench Report") -> str:
    total = len(records)
    passed = sum(1 for record in records if record.get("score", {}).get("passed"))
    errored = sum(1 for record in records if record.get("error"))
    avg_latency = _avg([record.get("latency_ms") for record in records if record.get("latency_ms") is not None])
    total_elapsed_ms = _run_elapsed_ms(records)
    usage_summary = _usage_summary(records)
    model_names = sorted({str(record.get("model", "unknown")) for record in records})
    suite_rows = "\n".join(_render_suite_row(suite, suite_records) for suite, suite_records in sorted(_group_by_suite(records).items()))
    failure_cards = "\n".join(_render_failure_card(record) for record in _failure_records(records))
    qa_cards = "\n".join(_render_qa_card(record) for record in records)
    case_rows = "\n".join(_render_case_row(record) for record in records)
    pass_rate = _percent(passed, total)
    avg_latency_text = f"{avg_latency:.0f} ms" if avg_latency is not None else "n/a"
    total_time_text = _format_duration(total_elapsed_ms)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{_escape(title)}</title>
  <style>
    :root {{
      --paper: #f6f1e7;
      --ink: #151310;
      --muted: #6b6254;
      --line: #d7ccb9;
      --panel: #fffaf0;
      --pass: #0b7a5f;
      --fail: #b23a48;
      --blue: #245c9a;
      --gold: #9b6900;
      --shadow: 0 14px 38px rgba(30, 22, 12, 0.10);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background:
        linear-gradient(90deg, rgba(21, 19, 16, 0.035) 1px, transparent 1px),
        linear-gradient(180deg, rgba(21, 19, 16, 0.035) 1px, transparent 1px),
        var(--paper);
      background-size: 28px 28px;
      color: var(--ink);
      font-family: "Avenir Next", "Noto Sans SC", "Source Han Sans SC", sans-serif;
      line-height: 1.5;
    }}

    header {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 30px 24px 16px;
    }}

    h1 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 38px;
      line-height: 1.06;
      letter-spacing: 0;
    }}

    .model {{
      margin-top: 10px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}

    .report-nav {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 0 24px 10px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .report-nav a {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--blue);
      font-weight: 700;
      padding: 6px 10px;
      text-decoration: none;
      box-shadow: var(--shadow);
    }}

    .report-nav a:hover {{
      text-decoration: underline;
    }}

    .summary {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 12px 24px 24px;
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 12px;
    }}

    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 250, 240, 0.94);
      box-shadow: var(--shadow);
      padding: 14px;
      min-height: 96px;
    }}

    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}

    .metric .value {{
      margin-top: 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 30px;
      line-height: 1;
    }}

    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 0 24px 32px;
    }}

    section {{
      margin-top: 20px;
    }}

    h2 {{
      font-size: 18px;
      margin: 0 0 10px;
      letter-spacing: 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}

    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      background: #efe5d5;
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    .status-pass {{
      color: var(--pass);
      font-weight: 700;
    }}

    .status-fail {{
      color: var(--fail);
      font-weight: 700;
    }}

    .failures {{
      display: grid;
      gap: 12px;
    }}

    .failure, .qa-card {{
      border: 1px solid var(--line);
      border-left: 5px solid var(--fail);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 14px;
    }}

    .qa-list {{
      display: grid;
      gap: 10px;
    }}

    .qa-card {{
      border-left-color: var(--blue);
      padding: 0;
      overflow: hidden;
    }}

    .qa-card summary {{
      cursor: pointer;
      padding: 12px 14px;
      list-style-position: inside;
      font-weight: 700;
    }}

    .qa-card[open] summary {{
      border-bottom: 1px solid var(--line);
      background: #f7eddd;
    }}

    .qa-body {{
      padding: 12px 14px 14px;
    }}

    .qa-meta {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}

    .failure h3 {{
      margin: 0 0 8px;
      font-size: 16px;
    }}

    .failure-label {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}

    .analysis {{
      margin-top: 8px;
      border: 1px solid #e3c977;
      border-left: 4px solid var(--gold);
      border-radius: 8px;
      background: #fff4cf;
      padding: 10px 12px;
      color: #3f3218;
    }}

    pre {{
      margin: 8px 0 0;
      max-height: 260px;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border-radius: 8px;
      background: #1d1a16;
      color: #f8ead0;
      padding: 10px;
    }}

    code, pre {{
      font-family: "SF Mono", "Cascadia Code", "Menlo", monospace;
      font-size: 13px;
    }}

    .controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}

    input[type="search"] {{
      width: min(460px, 100%);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px 12px;
      font: inherit;
    }}

    @media (max-width: 900px) {{
      .summary {{
        grid-template-columns: repeat(2, minmax(140px, 1fr));
      }}
    }}

    @media (max-width: 560px) {{
      .summary {{
        grid-template-columns: 1fr;
      }}

      table {{
        display: block;
        overflow-x: auto;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{_escape(title)}</h1>
    <div class="model">{_escape(", ".join(model_names))}</div>
  </header>
  <nav class="report-nav" aria-label="Report sections">
    <a href="#by-suite">By Suite</a>
    <a href="#failures">Failure Examples</a>
    <a href="#all-qa">All Questions &amp; Answers</a>
    <a href="#case-details">Case Details</a>
  </nav>
  <div class="summary">
      <div class="metric"><div class="label">Pass rate</div><div class="value">{pass_rate}</div></div>
      <div class="metric"><div class="label">Cases</div><div class="value">{passed}/{total}</div></div>
      <div class="metric"><div class="label">Avg latency</div><div class="value">{_escape(avg_latency_text)}</div></div>
      <div class="metric"><div class="label">Total time</div><div class="value">{_escape(total_time_text)}</div></div>
      <div class="metric"><div class="label">Total cost</div><div class="value">${usage_summary['cost']:.6f}</div></div>
      <div class="metric"><div class="label">Prompt tokens</div><div class="value">{usage_summary['prompt_tokens']}</div></div>
      <div class="metric"><div class="label">Completion tokens</div><div class="value">{usage_summary['completion_tokens']}</div></div>
    <div class="metric"><div class="label">Reasoning tokens</div><div class="value">{usage_summary['reasoning_tokens']}</div></div>
    <div class="metric"><div class="label">Errors</div><div class="value">{errored}</div></div>
  </div>
  <main>
    <section id="by-suite">
      <h2>By Suite</h2>
      <table>
        <thead><tr><th>Suite</th><th>Cases</th><th>Passed</th><th>Pass rate</th><th>Avg latency</th><th>Cost</th></tr></thead>
        <tbody>{suite_rows}</tbody>
      </table>
    </section>
    <section id="failures">
      <h2>Failure Examples</h2>
      <div class="failures">{failure_cards or '<p>No failures.</p>'}</div>
    </section>
    <section id="all-qa">
      <h2>All Questions &amp; Answers</h2>
      <div class="controls">
        <input id="qa-search" type="search" placeholder="Search prompt, expected answer, model answer, case id, suite">
      </div>
      <div class="qa-list" id="qa-list">{qa_cards}</div>
    </section>
    <section id="case-details">
      <h2>Case Details</h2>
      <div class="controls">
        <input id="search" type="search" placeholder="Search case id, suite, output">
      </div>
      <table id="case-table">
        <thead><tr><th>Case</th><th>Suite</th><th>Status</th><th>Failure Type</th><th>Score</th><th>Latency</th><th>Cost</th><th>Finish</th></tr></thead>
        <tbody>{case_rows}</tbody>
      </table>
    </section>
  </main>
  <script>
    const search = document.querySelector('#search');
    const rows = [...document.querySelectorAll('#case-table tbody tr')];
    search.addEventListener('input', () => {{
      const query = search.value.trim().toLowerCase();
      for (const row of rows) {{
        row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
      }}
    }});
    const qaSearch = document.querySelector('#qa-search');
    const qaCards = [...document.querySelectorAll('#qa-list details')];
    qaSearch.addEventListener('input', () => {{
      const query = qaSearch.value.trim().toLowerCase();
      for (const card of qaCards) {{
        const matched = !query || card.textContent.toLowerCase().includes(query);
        card.style.display = matched ? '' : 'none';
        if (query && matched) {{
          card.open = true;
        }}
      }}
    }});
  </script>
</body>
</html>
"""


def build_index_report(summaries: list[dict[str, Any]], title: str = "DracoBench Results Index") -> str:
    ordered = sorted(
        summaries,
        key=lambda item: (
            -int(item.get("case_count") or 0),
            -float(item.get("pass_rate_value") or 0),
            float(item.get("cost") or 0),
            str(item.get("model") or ""),
        ),
    )
    total_runs = len(ordered)
    best = ordered[0] if ordered else {}
    total_cost = sum(float(item.get("cost") or 0) for item in ordered)
    avg_pass_rate = _avg([float(item.get("pass_rate_value") or 0) for item in ordered])
    best_text = (
        f"{best.get('passed', 0)}/{best.get('case_count', 0)}"
        if best
        else "n/a"
    )
    chart_rows = "\n".join(_render_score_chart_row(item, index) for index, item in enumerate(ordered, start=1))
    rows = "\n".join(_render_index_row(item) for item in ordered)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>{_escape(title)}</title>
  <style>
    :root {{
      --paper: #f7f3ea;
      --ink: #171410;
      --muted: #70685d;
      --line: #d8ccba;
      --panel: #fffaf1;
      --panel-strong: #efe6d7;
      --pass: #0b765f;
      --fail: #ad3345;
      --link: #195f90;
      --shadow: 0 14px 34px rgba(31, 24, 15, 0.10);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23, 20, 16, 0.035) 1px, transparent 1px),
        linear-gradient(180deg, rgba(23, 20, 16, 0.035) 1px, transparent 1px),
        var(--paper);
      background-size: 28px 28px;
      font-family: "Avenir Next", "Noto Sans SC", "Source Han Sans SC", sans-serif;
      line-height: 1.5;
    }}

    header, main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 0 24px;
    }}

    header {{
      padding-top: 30px;
      padding-bottom: 14px;
    }}

    h1 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 38px;
      line-height: 1.08;
      letter-spacing: 0;
    }}

    .subhead {{
      margin-top: 8px;
      color: var(--muted);
    }}

    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin: 14px 0 22px;
    }}

    .metric {{
      min-height: 94px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 250, 241, 0.96);
      box-shadow: var(--shadow);
    }}

    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}

    .metric .value {{
      margin-top: 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 30px;
      line-height: 1;
    }}

    section {{
      margin: 20px 0 34px;
    }}

    h2 {{
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}

    .controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}

    input[type="search"] {{
      width: min(520px, 100%);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px 12px;
      font: inherit;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}

    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      background: var(--panel-strong);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      white-space: nowrap;
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    a {{
      color: var(--link);
      font-weight: 700;
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
    }}

    code {{
      font-family: "SF Mono", "Cascadia Code", "Menlo", monospace;
      font-size: 13px;
    }}

    .model-cell {{
      min-width: 250px;
      overflow-wrap: anywhere;
    }}

    .muted {{
      color: var(--muted);
      font-size: 12px;
    }}

    .status-pass {{
      color: var(--pass);
      font-weight: 700;
    }}

    .status-fail {{
      color: var(--fail);
      font-weight: 700;
    }}

    .badge {{
      display: inline-block;
      margin: 2px 4px 2px 0;
      padding: 2px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f7ecda;
      color: #4d463e;
      font-size: 12px;
      white-space: nowrap;
    }}

    .bar {{
      width: 100%;
      min-width: 120px;
      height: 8px;
      border-radius: 999px;
      background: #eadfce;
      overflow: hidden;
      margin-top: 6px;
    }}

    .bar span {{
      display: block;
      height: 100%;
      background: var(--pass);
    }}

    .token-cell {{
      min-width: 160px;
      white-space: nowrap;
    }}

    .token-row {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      line-height: 1.45;
    }}

    .token-label {{
      color: var(--muted);
      font-size: 12px;
    }}

    .note {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }}

    .ranking-chart {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 250, 241, 0.96);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .chart-row {{
      display: grid;
      grid-template-columns: 44px minmax(210px, 320px) minmax(240px, 1fr) 74px;
      gap: 12px;
      align-items: center;
      min-height: 50px;
      padding: 8px 14px;
      border-bottom: 1px solid var(--line);
    }}

    .chart-row:last-child {{
      border-bottom: 0;
    }}

    .chart-row.top-rank {{
      background: #fff3c4;
    }}

    .rank-pill {{
      width: 30px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #cfc5b5;
      border-radius: 50%;
      color: var(--muted);
      background: #fffdf8;
      font-weight: 700;
    }}

    .chart-model {{
      overflow-wrap: anywhere;
    }}

    .chart-track {{
      position: relative;
      min-height: 28px;
      border-left: 1px solid rgba(112, 104, 93, 0.16);
      background:
        linear-gradient(90deg, rgba(112, 104, 93, 0.13) 1px, transparent 1px),
        #f2eadc;
      background-size: 20% 100%;
      border-radius: 8px;
      overflow: hidden;
    }}

    .chart-bar {{
      display: block;
      height: 28px;
      min-width: 2px;
      border-radius: 7px;
      background: linear-gradient(90deg, #24418f, #0b765f);
    }}

    .chart-score {{
      font-family: "SF Mono", "Cascadia Code", "Menlo", monospace;
      color: #5f574d;
      font-weight: 700;
      white-space: nowrap;
    }}

    @media (max-width: 980px) {{
      .summary {{
        grid-template-columns: repeat(2, minmax(150px, 1fr));
      }}

      table {{
        display: block;
        overflow-x: auto;
      }}

      .chart-row {{
        grid-template-columns: 40px minmax(180px, 1fr) 70px;
      }}

      .chart-track {{
        grid-column: 2 / 4;
      }}
    }}

    @media (max-width: 560px) {{
      .summary {{
        grid-template-columns: 1fr;
      }}

      .chart-row {{
        grid-template-columns: 36px minmax(0, 1fr) 64px;
        gap: 8px;
        padding: 8px 10px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{_escape(title)}</h1>
    <div class="subhead">汇总已生成的 DracoBench 运行结果，点击模型名称进入逐题详情。生成日期：{generated_at}</div>
  </header>
  <main>
    <div class="summary">
      <div class="metric"><div class="label">Runs</div><div class="value">{total_runs}</div></div>
      <div class="metric"><div class="label">Best score</div><div class="value">{_escape(best_text)}</div></div>
      <div class="metric"><div class="label">Avg pass rate</div><div class="value">{_percent(avg_pass_rate or 0, 1) if avg_pass_rate is not None else "n/a"}</div></div>
      <div class="metric"><div class="label">Total cost</div><div class="value">${total_cost:.6f}</div></div>
    </div>
    <section>
      <h2>Score Ranking</h2>
      <div class="ranking-chart">{chart_rows or '<div class="chart-row">No runs found.</div>'}</div>
    </section>
    <section>
      <h2>Benchmark Results</h2>
      <div class="controls">
        <input id="search" type="search" placeholder="Search model, mode, suite, run file">
      </div>
      <p class="note">Latency 是平均单题延迟；Total Time 是根据逐题 started_at 和 latency_ms 估算的整轮运行耗时。Token Usage 汇总每次完整运行的输入、输出侧和 hidden reasoning 消耗：Prompt = 输入题目与系统提示；Completion = 输出侧总量；Reasoning = hidden thinking/reasoning token。</p>
      <table id="results-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Run</th>
            <th>Mode</th>
            <th>Score</th>
            <th>Suite Breakdown</th>
            <th>Latency</th>
            <th>Total Time</th>
            <th>Cost</th>
            <th>Token Usage</th>
            <th>Finish</th>
          </tr>
        </thead>
        <tbody>{rows or '<tr><td colspan="10">No runs found.</td></tr>'}</tbody>
      </table>
    </section>
  </main>
  <script>
    const search = document.querySelector('#search');
    const rows = [...document.querySelectorAll('#results-table tbody tr')];
    search.addEventListener('input', () => {{
      const query = search.value.trim().toLowerCase();
      for (const row of rows) {{
        row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
      }}
    }});
  </script>
</body>
</html>
"""


def summarize_run_file(run_path: Path | str, index_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(run_path)
    records = _load_jsonl(path)
    total = len(records)
    passed = sum(1 for record in records if record.get("score", {}).get("passed"))
    usage_summary = _usage_summary(records)
    avg_latency = _avg([record.get("latency_ms") for record in records if record.get("latency_ms") is not None])
    total_elapsed_ms = _run_elapsed_ms(records)
    model_names = sorted({str(record.get("model", "unknown")) for record in records})
    max_tokens = _common_value((record.get("parameters") or {}).get("max_tokens") for record in records)
    temperature = _common_value((record.get("parameters") or {}).get("temperature") for record in records)
    suite_summary = []
    for suite, suite_records in sorted(_group_by_suite(records).items()):
        suite_total = len(suite_records)
        suite_passed = sum(1 for record in suite_records if record.get("score", {}).get("passed"))
        suite_summary.append({"suite": suite, "passed": suite_passed, "total": suite_total})

    detail_path = _detail_html_path(path)
    base_dir = Path(index_path).parent if index_path else Path.cwd()
    detail_href = ""
    if detail_path.exists():
        detail_href = _report_site_href(detail_path, base_dir)

    return {
        "run_name": path.stem,
        "run_path": str(path),
        "run_href": _run_site_href(path, base_dir),
        "detail_path": str(detail_path) if detail_path.exists() else "",
        "detail_href": detail_href,
        "model": ", ".join(model_names),
        "case_count": total,
        "passed": passed,
        "pass_rate": _percent(passed, total),
        "pass_rate_value": passed / total if total else 0,
        "avg_latency_ms": avg_latency,
        "total_elapsed_ms": total_elapsed_ms,
        "cost": usage_summary["cost"],
        "prompt_tokens": usage_summary["prompt_tokens"],
        "completion_tokens": usage_summary["completion_tokens"],
        "reasoning_tokens": usage_summary["reasoning_tokens"],
        "finish_reasons": _finish_reason_summary(records),
        "suite_summary": suite_summary,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "mode": _infer_mode(path.stem, max_tokens),
        "rescored": path.stem.endswith("-rescored"),
    }


def select_preferred_run_paths(run_paths: list[Path]) -> list[Path]:
    existing = sorted({path for path in run_paths if path.exists() and path.suffix == ".jsonl"})
    rescored_bases = {path.with_name(path.stem.removesuffix("-rescored") + path.suffix) for path in existing if path.stem.endswith("-rescored")}
    selected = [path for path in existing if path.stem.endswith("-rescored") or path not in rescored_bases]
    return sorted(selected, key=lambda path: path.name)


def _render_score_chart_row(summary: dict[str, Any], rank: int) -> str:
    passed = int(summary.get("passed") or 0)
    total = int(summary.get("case_count") or 0)
    pass_rate_value = max(0.0, min(1.0, float(summary.get("pass_rate_value") or 0)))
    width = pass_rate_value * 100
    model_text = _escape(summary.get("model", "unknown"))
    detail_href = str(summary.get("detail_href") or "")
    model_link = f"<a href=\"{_escape(detail_href)}\">{model_text}</a>" if detail_href else model_text
    top_class = " top-rank" if rank == 1 else ""
    score_text = f"{passed}/{total}"
    return f"""<div class="chart-row{top_class}">
  <div><span class="rank-pill">{rank}</span></div>
  <div class="chart-model">{model_link}</div>
  <div class="chart-track" aria-label="{_escape(model_text)} score {score_text}"><span class="chart-bar" style="width: {width:.1f}%"></span></div>
  <div class="chart-score">{score_text}</div>
</div>"""


def _render_index_row(summary: dict[str, Any]) -> str:
    passed = int(summary.get("passed") or 0)
    total = int(summary.get("case_count") or 0)
    pass_rate_value = float(summary.get("pass_rate_value") or 0)
    avg_latency = summary.get("avg_latency_ms")
    latency_text = f"{avg_latency:.0f} ms" if avg_latency is not None else "n/a"
    total_time_text = _format_duration(summary.get("total_elapsed_ms"))
    token_text = _render_token_usage(summary)
    suite_badges = " ".join(
        f"<span class=\"badge\">{_escape(item['suite'])} {int(item['passed'])}/{int(item['total'])}</span>"
        for item in summary.get("suite_summary", [])
    )
    model_text = _escape(summary.get("model", "unknown"))
    detail_href = str(summary.get("detail_href") or "")
    model_link = f"<a href=\"{_escape(detail_href)}\">{model_text}</a>" if detail_href else model_text
    status_class = "status-pass" if passed == total else "status-fail"
    rescored_badge = " <span class=\"badge\">rescored</span>" if summary.get("rescored") else ""
    mode_parts = [_escape(summary.get("mode", "unknown"))]
    if summary.get("temperature") is not None:
        mode_parts.append(f"temp={_escape(summary.get('temperature'))}")
    finish_text = ", ".join(f"{key}:{value}" for key, value in summary.get("finish_reasons", {}).items())
    return f"""<tr>
  <td class="model-cell">{model_link}<div class="muted"><code>{_escape(summary.get('run_name', 'unknown'))}</code>{rescored_badge}</div></td>
  <td><a href="{_escape(summary.get('run_href', ''))}">JSONL</a></td>
  <td>{'<br>'.join(mode_parts)}</td>
  <td><span class="{status_class}">{passed}/{total}</span><div>{_escape(summary.get('pass_rate', 'n/a'))}</div><div class="bar"><span style="width: {pass_rate_value * 100:.1f}%"></span></div></td>
  <td>{suite_badges}</td>
  <td>{_escape(latency_text)}</td>
  <td>{_escape(total_time_text)}</td>
  <td>${float(summary.get('cost') or 0):.6f}</td>
  <td class="token-cell">{token_text}</td>
  <td>{_escape(finish_text)}</td>
</tr>"""


def _render_token_usage(summary: dict[str, Any]) -> str:
    items = [
        ("Prompt", summary.get("prompt_tokens", 0)),
        ("Completion", summary.get("completion_tokens", 0)),
        ("Reasoning", summary.get("reasoning_tokens", 0)),
    ]
    return "".join(
        f"<div class=\"token-row\"><span class=\"token-label\">{label}</span><span>{_escape(value)}</span></div>"
        for label, value in items
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _detail_html_path(run_path: Path) -> Path:
    if run_path.parent.name == "runs":
        return run_path.parent.parent / "reports" / f"{run_path.stem}.html"
    return run_path.with_suffix(".html")


def _report_site_href(path: Path, base_dir: Path) -> str:
    if path.parent.name == "reports":
        return f"/reports/{path.name}"
    return _relative_href(path, base_dir)


def _run_site_href(path: Path, base_dir: Path) -> str:
    if path.parent.name == "runs":
        return f"/runs/{path.name}"
    return _relative_href(path, base_dir)


def _relative_href(path: Path, base_dir: Path) -> str:
    return os.path.relpath(path, start=base_dir).replace(os.sep, "/")


def _common_value(values: Any) -> Any:
    items = [item for item in values if item is not None]
    if not items:
        return None
    first = items[0]
    if all(item == first for item in items):
        return first
    return "mixed"


def _finish_reason_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for record in records:
        summary[str(record.get("finish_reason") or "unknown")] += 1
    return dict(sorted(summary.items()))


def _infer_mode(run_name: str, max_tokens: Any) -> str:
    match = re.search(r"(ability|efficiency)(\d+)", run_name)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    if max_tokens is None:
        return "unknown"
    return f"max_tokens={max_tokens}"


def _group_by_suite(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("suite", "unknown"))].append(record)
    return grouped


def _render_suite_row(suite: str, records: list[dict[str, Any]]) -> str:
    total = len(records)
    passed = sum(1 for record in records if record.get("score", {}).get("passed"))
    avg_latency = _avg([record.get("latency_ms") for record in records if record.get("latency_ms") is not None])
    usage_summary = _usage_summary(records)
    latency_text = f"{avg_latency:.0f} ms" if avg_latency is not None else "n/a"
    return (
        f"<tr data-suite=\"{_escape(suite)}\"><td><code>{_escape(suite)}</code></td>"
        f"<td>{total}</td><td>{passed}</td><td>{_percent(passed, total)}</td>"
        f"<td>{_escape(latency_text)}</td><td>${usage_summary['cost']:.6f}</td></tr>"
    )


def _render_case_row(record: dict[str, Any]) -> str:
    score = record.get("score") or {}
    usage = record.get("usage") or {}
    passed = bool(score.get("passed"))
    status_class = "status-pass" if passed else "status-fail"
    status = "PASS" if passed else "FAIL"
    latency = record.get("latency_ms")
    latency_text = f"{latency} ms" if latency is not None else "n/a"
    failure_type = _failure_type(record)
    failure_type_text = "-" if failure_type == "pass" else failure_type
    return (
        f"<tr data-suite=\"{_escape(record.get('suite', 'unknown'))}\">"
        f"<td><code>{_escape(record.get('case_id', 'unknown'))}</code></td>"
        f"<td>{_escape(record.get('suite', 'unknown'))}</td>"
        f"<td class=\"{status_class}\">{status}</td>"
        f"<td><code>{_escape(failure_type_text)}</code></td>"
        f"<td>{_escape(score.get('score', 0))}</td>"
        f"<td>{_escape(latency_text)}</td>"
        f"<td>${float(usage.get('cost') or 0):.6f}</td>"
        f"<td>{_escape(record.get('finish_reason'))}</td>"
        "</tr>"
    )


def _render_qa_card(record: dict[str, Any]) -> str:
    score = record.get("score") or {}
    usage = record.get("usage") or {}
    passed = bool(score.get("passed"))
    status_class = "status-pass" if passed else "status-fail"
    status = "PASS" if passed else "FAIL"
    prompt = str(record.get("prompt", "")).strip()
    output = str(record.get("output", "")).strip()
    expected_block = _render_expected_block(record)
    analysis_block = _render_analysis_block(record) if not passed or record.get("error") or _has_manual_review_override(record) else ""
    case_id = str(record.get("case_id", "unknown"))
    suite = str(record.get("suite", "unknown"))
    latency = record.get("latency_ms")
    latency_text = f"{latency} ms" if latency is not None else "n/a"
    return f"""<details class="qa-card" id="qa-{_escape(case_id)}" data-suite="{_escape(suite)}">
  <summary><code>{_escape(case_id)}</code> <span class="{status_class}">{status}</span></summary>
  <div class="qa-body">
    <div class="qa-meta">Suite: <code>{_escape(suite)}</code> · Latency: {_escape(latency_text)} · Cost: ${float(usage.get('cost') or 0):.6f} · Finish: <code>{_escape(record.get('finish_reason'))}</code></div>
    <div class="failure-label">Prompt</div>
    <pre>{_escape(prompt)}</pre>
    {expected_block}
    {analysis_block}
    <div class="failure-label">Output</div>
    <pre>{_escape(output)}</pre>
  </div>
</details>"""


def _render_failure_card(record: dict[str, Any]) -> str:
    score = record.get("score") or {}
    details = json.dumps(score.get("details") or {}, ensure_ascii=False, indent=2)
    error = json.dumps(record.get("error"), ensure_ascii=False, indent=2) if record.get("error") else ""
    output = str(record.get("output", "")).strip()
    prompt = str(record.get("prompt", "")).strip()
    diagnostic = error or details
    expected_block = _render_expected_block(record)
    prompt_block = ""
    if prompt:
        prompt_block = f"""
  <div class="failure-label">Prompt</div>
  <pre>{_escape(prompt)}</pre>"""
    analysis = explain_failure(record)
    return f"""<article class="failure" data-suite="{_escape(record.get('suite', 'unknown'))}">
  <h3>{_escape(record.get('case_id', 'unknown'))}</h3>
  <div>Suite: <code>{_escape(record.get('suite', 'unknown'))}</code></div>
  <div>Finish: <code>{_escape(record.get('finish_reason'))}</code></div>
  {prompt_block}
  {expected_block}
  {_render_analysis_block(record, analysis)}
  <div class="failure-label">Scorer Details</div>
  <pre>{_escape(diagnostic)}</pre>
  <div class="failure-label">Output</div>
  <pre>{_escape(output[:1800])}</pre>
</article>"""


def _render_analysis_block(record: dict[str, Any], analysis: str | None = None) -> str:
    failure_type = _failure_type(record)
    label = "Manual Review" if _has_manual_review_override(record) else "Mistake Analysis"
    explanation = analysis if analysis is not None else explain_failure(record)
    return f"""
    <div class="failure-label">{label}</div>
    <div class="analysis">
      <div><strong>Failure type:</strong> <code>{_escape(failure_type)}</code></div>
      <div>{_escape(explanation)}</div>
    </div>"""


def _render_expected_block(record: dict[str, Any]) -> str:
    expected_text = _format_expected(record)
    if not expected_text:
        return ""
    return f"""
    <div class="failure-label">Standard Answer / Scoring Expectation</div>
    <pre>{_escape(expected_text)}</pre>"""


def _format_expected(record: dict[str, Any]) -> str:
    expected = record.get("expected")
    if not isinstance(expected, dict):
        return ""
    scorer = str(record.get("scorer") or "")

    if scorer == "exact":
        return f"Answer: {expected.get('answer')}"

    if scorer == "contains_any":
        answers = expected.get("answers") or []
        return "Accepted answers:\n" + "\n".join(f"- {answer}" for answer in answers)

    if scorer == "regex":
        return "Expected regex pattern:\n" + str(expected.get("pattern"))

    if scorer == "json_schema_lite":
        return "Expected JSON schema:\n" + json.dumps(expected.get("schema") or expected, ensure_ascii=False, indent=2)

    if scorer == "text_rules":
        lines = []
        required = expected.get("required") or []
        required_any = expected.get("required_any") or []
        forbidden = expected.get("forbidden") or []
        if required:
            lines.append("Required phrases: " + "、".join(str(item) for item in required))
        if required_any:
            groups = [" / ".join(str(option) for option in group) for group in required_any]
            lines.append("At least one from each group: " + "；".join(groups))
        if forbidden:
            lines.append("Forbidden phrases: " + "、".join(str(item) for item in forbidden))
        if "min_chars" in expected or "max_chars" in expected:
            lines.append(
                "Length guidance (diagnostic only): "
                f"min={expected.get('min_chars', 'n/a')}, max={expected.get('max_chars', 'n/a')}"
            )
        return "\n".join(lines) or json.dumps(expected, ensure_ascii=False, indent=2)

    if scorer == "code_python_tests":
        tests = expected.get("tests") or []
        return "Reference tests:\n" + "\n".join(str(test) for test in tests)

    return json.dumps(expected, ensure_ascii=False, indent=2)


def _failure_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if not record.get("score", {}).get("passed") or record.get("error")]


def explain_failure(record: dict[str, Any]) -> str:
    if record.get("failure_explanation"):
        return str(record["failure_explanation"])

    score = record.get("score") or {}
    details = score.get("details") or {}
    if details.get("manual_review_override"):
        reason = str(details.get("reason") or "").strip()
        if reason:
            return reason
        return "这道题原始 scorer 判为失败，但人工复核认为模型答案满足题意，因此在 rescored 结果中改判通过。"

    prompt = str(record.get("prompt") or "")
    output = str(record.get("output") or "")
    stderr = str(details.get("stderr") or "")
    finish_reason = record.get("finish_reason")
    failure_type = _failure_type(record)

    known_explanation = _known_root_cause(record, failure_type)
    if known_explanation:
        return known_explanation

    if record.get("error"):
        return "这道题没有进入正常判分流程，失败来自 API 调用、运行器或评分器错误。需要先查看 error 字段，而不是直接归因于模型能力。"

    if finish_reason == "length" and not output.strip():
        return "模型把可用输出预算耗尽了，但没有产出可评分正文，形成空输出。这更像 token budget 或过度思考问题，不应简单等同于不会做题。"

    if failure_type == "degenerate_output":
        return (
            "模型输出退化成大量无意义片段或内部标记，正文既不是题目要求的最终答案，也不是可运行代码。"
            "这通常是解码/路由稳定性问题，根因不在具体题目逻辑，而在答案生成阶段失控。"
        )

    if failure_type == "duplicate_answer":
        expected, actual = _exact_answer_pair(record)
        repeat_count = _answer_repeat_count(actual, expected)
        repeat_text = f"{repeat_count} 次" if repeat_count else "多次"
        return (
            f"标准答案是 `{_short_text(expected)}`，模型输出 `{_short_text(actual)}`，"
            f"等于把标准答案连续输出了 {repeat_text}。这更像短答案格式发射/指令遵循问题，"
            "不是核心推理错误；严格 exact scorer 仍会按失败计。"
        )

    if failure_type == "format_violation":
        expected, actual = _exact_answer_pair(record)
        return (
            f"核心答案可以还原为标准答案 `{_short_text(expected)}`，但模型输出为 `{_short_text(actual)}`，"
            "包含 Markdown、解释或其他多余内容。题目要求只输出最终答案，因此严格 exact scorer 判失败。"
        )

    if failure_type == "answer_mismatch":
        expected, actual = _exact_answer_pair(record)
        return (
            f"模型最终答案 `{_short_text(actual)}` 与标准答案 `{_short_text(expected)}` 不一致；"
            "去除常见 Markdown 包裹后仍不相等，属于核心答案错误，而不是单纯格式问题。"
        )

    if failure_type == "duplicate_json_object":
        count = len(_json_sequence_values(output))
        validity = _json_sequence_schema_validity(record)
        validity_text = "每个对象单独看都符合 schema；" if validity == "all_valid" else ""
        return (
            f"题目要求只输出一个 JSON 对象，但模型连续输出了 {count} 个 JSON 对象。"
            f"{validity_text}整体字符串不是合法 JSON，解析器在第一个对象结束后又遇到额外内容，"
            "因此报 `Extra data`。根因是结构化输出重复发射，不是字段值本身错误。"
        )

    if failure_type == "multiple_json_values":
        count = len(_json_sequence_values(output))
        return (
            f"题目要求只输出一个 JSON 对象，但模型输出了 {count} 个可解析的 JSON 值。"
            "JSON schema 评分只能接受单一根对象，多个值背靠背会让解析器报额外数据。"
        )

    if failure_type == "json_parse_error":
        error = str(details.get("error") or "unknown JSON parse error")
        return (
            f"模型输出没有形成合法 JSON，因此 schema 校验还没开始就失败了。解析错误为：`{_short_text(error)}`。"
            "这通常来自多余说明文字、残缺括号、未转义字符或多个 JSON 片段。"
        )

    if failure_type.startswith("schema_"):
        schema_errors = [str(item) for item in (details.get("errors") or [])]
        first_error = schema_errors[0] if schema_errors else "unknown schema error"
        return (
            "模型输出是可解析 JSON，但字段结构或取值没有满足题目 schema。"
            f"首个具体错误是：`{_short_text(first_error)}`。"
        )

    if "has no attribute 'solve'" in stderr:
        if finish_reason == "length" or not output.strip():
            return "模型没有输出题目要求的 solve 函数，通常是输出预算被耗尽或正文为空，导致代码测试无法找到入口函数。"
        return "模型输出了代码，但没有按题目约定定义 solve 函数，导致测试无法调用指定入口。"

    if "ValueError: invalid literal for int()" in stderr:
        if "key" in prompt.lower() and "int(parts[1])" in output:
            return "模型把题目中的 key 错误假设为整数，并对 parts[1] 做 int 转换；测试使用字符串 key，因此在解析 'a' 这类 key 时直接抛出 ValueError。"
        return "模型对输入字段类型做了错误假设，把非数字内容当成整数解析，导致运行时 ValueError。"

    if "AssertionError" in stderr:
        if "sorted(best.items())" in output and "user" in prompt:
            return "模型大体找到了每个 user 的候选记录，但返回列表时排序/解包结构错误，把内部保存的元组结构带进了最终输出，导致结果和期望不一致。"
        return "模型代码可以运行，但至少一个单元测试断言失败，说明逻辑结果不符合题目要求。"

    missing = details.get("missing") or []
    if missing:
        return "模型输出缺少评分规则要求的关键信息：" + "、".join(str(item) for item in missing) + "。"

    forbidden = details.get("present_forbidden") or []
    if forbidden:
        return "模型输出包含题目明确禁止的内容：" + "、".join(str(item) for item in forbidden) + "。"

    if details.get("length_ok") is False:
        return "模型答案内容方向可能正确，但没有满足长度约束，因此被判为失败。"

    schema_errors = details.get("errors") or []
    if schema_errors:
        return "模型输出没有通过结构化 schema 校验，主要问题是：" + "; ".join(str(item) for item in schema_errors[:3])

    if failure_type == "regex_miss":
        return _regex_miss_explanation(record)

    if failure_type == "missing_accepted_answer":
        return _contains_any_miss_explanation(record)

    if details.get("matched") == []:
        return _contains_any_miss_explanation(record)

    return _generic_scorer_miss_explanation(record, failure_type)


def _failure_type(record: dict[str, Any]) -> str:
    if record.get("failure_type"):
        return str(record["failure_type"])
    if _has_manual_review_override(record):
        return "manual_review_override"
    if not record.get("error") and record.get("score", {}).get("passed"):
        return "pass"
    if record.get("error"):
        error = record.get("error") or {}
        if isinstance(error, dict) and error.get("type") == "api_wall_timeout":
            return "api_timeout_no_answer"
        return "runner_or_api_error"

    score = record.get("score") or {}
    details = score.get("details") or {}
    output = str(record.get("output") or "")
    stderr = str(details.get("stderr") or "")
    finish_reason = record.get("finish_reason")
    scorer = str(record.get("scorer") or "")

    if not output.strip():
        if finish_reason == "length":
            return "empty_output_length"
        return "empty_output"
    if _looks_like_degenerate_output(output):
        return "degenerate_output"

    if scorer == "exact":
        return _exact_failure_type(record)

    if scorer == "json_schema_lite":
        return _json_failure_type(record)

    if scorer == "text_rules":
        if details.get("missing") or details.get("missing_any"):
            return "missing_required_info"
        if details.get("present_forbidden"):
            return "forbidden_content"
        if details.get("length_ok") is False:
            return "length_guidance_miss"
        return "text_rule_miss"

    if scorer == "contains_any":
        return "missing_accepted_answer"

    if scorer == "regex":
        return "regex_miss"

    if scorer == "code_python_tests":
        if details.get("error") == "timeout":
            return "code_timeout"
        if "SyntaxError" in stderr or "IndentationError" in stderr:
            return "code_syntax_error"
        if "has no attribute 'solve'" in stderr:
            return "missing_solve_function"
        if "ValueError: invalid literal for int()" in stderr:
            return "runtime_type_assumption"
        if "AssertionError" in stderr:
            return "code_assertion_failure"
        if "TypeError" in stderr:
            return "code_type_error"
        return "code_execution_failure"

    return "scorer_miss"


def _has_manual_review_override(record: dict[str, Any]) -> bool:
    details = (record.get("score") or {}).get("details") or {}
    return bool(details.get("manual_review_override"))


def _json_failure_type(record: dict[str, Any]) -> str:
    score = record.get("score") or {}
    details = score.get("details") or {}
    error = str(details.get("error") or "")
    schema_errors = [str(item) for item in (details.get("errors") or [])]

    if error:
        values = _json_sequence_values(str(record.get("output") or ""))
        if len(values) > 1:
            if all(_json_values_equal(value, values[0]) for value in values[1:]):
                return "duplicate_json_object"
            return "multiple_json_values"
        return "json_parse_error"

    if not schema_errors:
        return "schema_violation"

    if any("missing required field" in item for item in schema_errors):
        return "schema_missing_required"
    if any("unexpected field" in item for item in schema_errors):
        return "schema_unexpected_field"
    if any("expected const" in item for item in schema_errors):
        return "schema_const_mismatch"
    if any("expected one of" in item for item in schema_errors):
        return "schema_enum_mismatch"
    if any("expected " in item and " got " in item for item in schema_errors):
        return "schema_type_mismatch"
    if any("does not match pattern" in item for item in schema_errors):
        return "schema_pattern_mismatch"
    if any("expected at least" in item or "expected at most" in item for item in schema_errors):
        return "schema_array_length_mismatch"
    return "schema_violation"


def _known_root_cause(record: dict[str, Any], failure_type: str) -> str | None:
    scorer = str(record.get("scorer") or "")
    case_id = str(record.get("case_id") or "")

    if failure_type == "api_timeout_no_answer":
        return (
            "OpenRouter 调用超过 300 秒后被运行器中止，模型没有返回可评分正文。"
            "后续代码测试只能拿到空文件，因此报找不到 `solve`。根因是 API/模型响应超时，不是该题算法逻辑被判错。"
        )

    if case_id == "challenge-rag-014" and not str(record.get("output") or "").strip():
        return (
            "题目问当前总览页对应的 token limit，资料 B/C 都指向 `ability16384`，应回答 16384。"
            "模型返回了空字符串，导致关键数字完全缺失。根因是正常 stop 但未产出正文，不是资料检索歧义。"
        )

    if failure_type == "empty_output_length":
        return (
            "模型耗尽输出预算后没有留下任何正文，形成空输出。评分器无法找到答案或 `solve` 函数，所以失败。"
            "这类问题应归因于输出预算/过度生成，而不是某个具体算法步骤写错。"
        )

    if failure_type == "empty_output":
        return (
            "模型正常结束但没有输出任何可评分正文，形成空输出。评分器无法命中答案或关键字段，"
            "因此失败。根因是答案生成阶段没有产出内容，而不是评分规则过严。"
        )

    if failure_type == "degenerate_output":
        return _degenerate_output_explanation(record)

    if scorer == "code_python_tests":
        return _known_code_root_cause(record, failure_type)

    if scorer == "regex":
        return _known_regex_root_cause(record)

    if scorer == "contains_any":
        return _known_contains_any_root_cause(record)

    if scorer == "exact" and failure_type == "answer_mismatch":
        return _known_exact_root_cause(record)

    if scorer == "text_rules":
        return _known_text_rule_root_cause(record)

    return None


def _known_code_root_cause(record: dict[str, Any], failure_type: str) -> str | None:
    case_id = str(record.get("case_id") or "")
    output = str(record.get("output") or "")

    if case_id == "challenge-coding-002":
        return (
            "撤销交易的方向处理错了。代码把 credit 和 debit 都存成正数 amount，撤销时统一执行 `balance -= amount`；"
            "撤销 credit 应该减钱，但撤销 debit 应该把扣掉的钱加回来。第一组用例里 `rev b` 应抵消 `b debit 40`，"
            "模型反而又减了 40，最终余额从应为 90 变成 10。"
        )

    if case_id == "challenge-coding-004":
        return (
            "题目里的 cache key 是字符串，例如 `a`、`b`、`c`，但模型把 key 强行写成 `int(parts[1])`。"
            "测试一遇到 `put a 1` 就在解析 `a` 时抛出 ValueError。根因是模型擅自补了“key 是整数”的类型假设。"
        )

    if case_id == "challenge-coding-014":
        return (
            "模型采用了左右最大子数组拼接法，但没有正确覆盖“删除后可以只取一侧子数组”的情况。"
            "在 `[1,-2,-2,3]` 中，最佳做法是删除一个 `-2` 后取右侧 `[3]`，答案为 3；"
            "模型只算出 2，说明动态规划状态没有完整表达“恰好删除一个元素后的最大连续和”。"
        )

    if case_id == "challenge-coding-018":
        return (
            "路径规范化的主体逻辑基本正确，但根目录边界处理错了。`'/' + '/'.join([])` 得到 `/` 后，"
            "代码又执行 `result.rstrip('/')`，把根目录唯一的斜杠也删掉，导致 `solve('/')` 返回空字符串而不是 `/`。"
        )

    if case_id == "challenge-coding-026":
        if not output.strip() or failure_type == "empty_output_length":
            return (
                "模型在滑动窗口中位数题上耗尽输出预算且没有输出代码，测试文件里自然找不到 `solve`。"
                "这是未完成作答/空输出，不是某一行算法实现失败。"
            )
        return (
            "双堆思路方向正确，但懒删除实现没有维护两个堆的“有效元素数量”。"
            "窗口滑动时旧元素只记在 `to_remove`，堆的物理长度仍参与 `balance()`，导致堆大小和真实窗口分布不同步；"
            "后半段窗口的中位数被旧元素/错误堆顶影响，第一组期望 `[1,-1,-1,3,5,6]`，模型给出后几项偏小。"
        )

    if case_id == "challenge-coding-010":
        return (
            "表达式解析器没有在读取运算符前跳过空格。解析完 `1` 后，指针停在空格上，"
            "`while expr[i] in '+-'` 直接结束，导致 `1 + 2 - 3` 只返回 1 而不是继续计算到 0。"
            "根因是词法扫描对空白字符处理不一致。"
        )

    if case_id == "challenge-coding-015":
        return (
            "CSV 解析在引号字段结束后只接受紧跟逗号，没有把引号后的普通空格作为字段内容保留下来。"
            "第三个测试里 `\" b \" ` 的结束引号后还有一个空格，期望字段是 ` b  `；"
            "模型输出漏掉了尾随空格，违反了题目“空格是普通字符，不要 trim”的要求。"
        )

    if case_id == "challenge-coding-027":
        if "TypeError" in str((record.get("score") or {}).get("details", {}).get("stderr") or ""):
            return (
                "版本排序 key 的最后一项有时是字符串 label，有时是 `None`。Python 排序比较同一数字版本时会尝试比较 "
                "`'alpha'` 和 `None`，直接抛出 TypeError。根因是没有把正式版和预发布版映射到同一类型的可比较 key；"
                "应显式让预发布版低于正式版，例如用 `(has_no_label, label)` 这类布尔/字符串组合。"
            )
        return (
            "版本排序方向写反了。题目要求同一数字版本下预发布版低于正式版，但模型的 key 是 "
            "`(numeric, 0 if label is None else 1, label)`，升序排序会把正式版 `1.0.0` 放在 "
            "`1.0.0-alpha` 和 `1.0.0-beta` 前面。根因是正式版/预发布版的排序标志位取值反了；"
            "应让带 label 的版本排在正式版之前，并为正式版使用可比较的占位 label。"
        )

    if case_id == "challenge-coding-016":
        return (
            "区间合并思路本身接近正确，但生成的 Python 缩进坏了：`if start <= current_end + 1:` "
            "下一行 `current_end = max(current_end, end)` 没有缩进到 if 块内，导入 `solution.py` 时直接抛 "
            "IndentationError。根因是代码格式/缩进损坏，不是区间合并条件本身被测试击穿。"
        )

    if case_id == "challenge-coding-021":
        return (
            "频次统计方向正确，但“第一次出现位置”的记录方式错了。代码用字典推导 "
            "`{item: idx for idx, item in enumerate(items)}`，重复元素会被后面的索引覆盖，实际记录的是最后一次出现位置。"
            "第二组里 x、y、z 都出现 2 次，正确 tie-break 应按第一次出现得到 `[x, y]`；模型按最后出现位置排序成 `[y, z]`。"
            "根因是 tie-break 状态记录错，应只在元素第一次出现时写入索引。"
        )

    if case_id == "challenge-coding-003":
        return (
            "拓扑分层题没有得到可执行实现：运行记录显示 API 超时/空输出，测试导入的 `solution.py` 中没有 `solve`。"
            "因此失败点是没有完成代码生成，而不是拓扑排序逻辑被具体用例击穿。"
        )

    if case_id == "challenge-coding-007":
        return (
            "模型输出不是 Python 代码，而是大量类似 `</think>`、`</arg_value>` 的内部标记和乱码。"
            "导入 `solution.py` 时第一行就触发 SyntaxError。根因是答案生成退化/内部标记泄漏，尚未进入括号匹配算法本身。"
        )

    return None


def _known_regex_root_cause(record: dict[str, Any]) -> str | None:
    case_id = str(record.get("case_id") or "")
    output = str(record.get("output") or "")

    if case_id == "challenge-debugging-001":
        return (
            "模型正确指出默认参数里的 iterator 会在第一次调用后被耗尽，但最后的 `FIX:` 行写成了 "
            "`def summarize(items=[1, 2, 3])`。当前 benchmark 期望的最小修复是把函数头改成 "
            "`def summarize(items=None):`，再在函数体内创建默认列表/迭代器。根因是模型修复了症状，"
            "但最终修复行没有采用标准的 None sentinel 写法，也引入了不推荐的可变默认参数形式。"
        )

    if case_id == "challenge-debugging-003":
        return (
            "模型已经定位到 `range` 的 stop 参数应从 `len(items) - page_size` 改为 `len(items)`，核心 bug 判断正确。"
            "但题目要求最后单独输出“修复后的 range 行”，当前 regex 期望完整代码行 "
            "`for start in range(0, len(items), page_size):`；模型只写了 `FIX: range(0, len(items), page_size)`，"
            "缺少 `for start in` 和结尾冒号，因此被判为 regex miss。根因是最终 FIX 行格式不完整，而不是分页逻辑没看懂。"
        )

    if case_id == "challenge-debugging-005":
        return (
            "模型正确知道缓存 key 必须包含调用参数，也把 kwargs 排序后放进 key 里；失败点在最终 key 形式。"
            "当前标准答案期望 `key = (fn.__name__, args, tuple(sorted(kwargs.items())))` 或等价 frozenset 写法，"
            "模型输出的是 `key = (fn, args, tuple(sorted(kwargs.items())))`。用函数对象 `fn` 在很多场景下也能区分函数，"
            "但没有命中本题的固定 regex。根因更偏评分模式未覆盖这个等价实现，而不是模型完全没修好缓存参数混淆。"
        )

    if output.strip():
        return _regex_miss_explanation(record)
    return None


def _known_contains_any_root_cause(record: dict[str, Any]) -> str | None:
    case_id = str(record.get("case_id") or "")
    output = str(record.get("output") or "")

    if case_id == "challenge-debugging-008":
        return (
            "模型正确指出 `finally` 里的 `return None` 会覆盖 `try` 中的 `return 42`，修复方向也是删除这个 return。"
            "失败点在最后的 `FIX:` 行只写了 `删除 return None`，没有明确说“删除 finally 中的 return None”。"
            "当前 contains_any scorer 只接受包含 finally 位置的固定表达；模型正文里虽解释了 finally，但最终短答案没有命中可接受短语。"
            "根因是最终修复说明过短/评分短语覆盖不足，而不是调试判断错误。"
        )

    if output.strip():
        return _contains_any_miss_explanation(record)
    return None


def _known_exact_root_cause(record: dict[str, Any]) -> str | None:
    case_id = str(record.get("case_id") or "")
    expected, actual = _exact_answer_pair(record)
    derivations = {
        "challenge-reasoning-001": (
            "正确链路是 A=6，B=4，C=8，D=(6+8)/2=7；每分钟总量 25，5 分钟总量 125。"
            f"模型输出 `{_short_text(actual)}`，说明它在多步算术链路中把某个服务速率或总时长重复计入了。"
        ),
        "challenge-reasoning-002": (
            "字典序最小的合法队列是 `A B D C E`：A<B<C，E 紧跟 C，且 D 不在两端。"
            f"第三个任务应为 D，模型输出 `{_short_text(actual)}`，根因是约束排序时没有把 D 的位置限制和字典序最小同时满足。"
        ),
        "challenge-reasoning-003": (
            "1011 左移一位并只保留低 4 位得到 0110；0110 XOR 0110 = 0000，十进制为 0。"
            f"模型输出 `{_short_text(actual)}`，说明它漏掉了“只保留低 4 位”或在 XOR 步骤中按位计算错误。"
        ),
        "challenge-reasoning-011": (
            "列表按位置相减得到 `[1,2,3,4]`，删除奇数后是 `[2,4]`，平方求和为 4+16=20。"
            f"模型输出 `{_short_text(actual)}`，根因是状态变换顺序或“删除奇数”步骤处理错。"
        ),
        "challenge-reasoning-012": (
            "10110 循环右移 1 位得到 01011；01011 XOR 00111 = 01100，十进制为 12。"
            f"模型输出 `{_short_text(actual)}`，根因是循环移位或 XOR 的二进制位计算错。"
        ),
        "challenge-reasoning-013": (
            "通过题数/成本分别为 A=18/0.06=300，B=20/0.10=200，C=16/0.04=400。"
            f"最高是 C，模型输出 `{_short_text(actual)}`，说明它更看重通过题数绝对值，而没有按题目要求计算性价比。"
        ),
        "challenge-reasoning-015": (
            "正确集合变化是 `{a,b,c,d}` 删除 c 之前的 a,b 得 `{c,d}`；加入 e,b 得 `{b,c,d,e}`；"
            "再删除元音 e，剩 `{b,c,d}`，数量为 3。模型没有输出数字答案，根因是生成阶段失控而不是集合操作推理。"
        ),
        "challenge-reasoning-017": (
            "拓扑层应为第一层 `{a}`，第二层 `{b,c,g}`，因为 b、c、g 都只依赖 a。"
            f"第二层有 3 个任务，模型输出 `{_short_text(actual)}`，通常是漏掉了同样只依赖 a 的 `g`。"
        ),
        "challenge-reasoning-019": (
            "恰好一个 A：A 在末位时前两位可为 B/C 共 4 种；A 在第 1 或第 2 位时末位只能是 B，各 2 种；总数 8。"
            f"模型输出 `{_short_text(actual)}`，说明它漏算了某些 A 的位置，或错误处理了“最后一个字符不能是 C”的限制。"
        ),
        "challenge-reasoning-020": (
            "栈执行到 `push 4, swap` 后为 `[2,4,6]`；`sub` 先弹 x=6，再弹 y=4，压入 y-x=-2。"
            f"模型输出 `{_short_text(actual)}`，根因是 `sub` 的出栈顺序或 `swap` 后栈顶理解错。"
        ),
        "challenge-reasoning-022": (
            "映射更新后 c=3，a=c-b=1，删除 b，再设置 d=a+c=4；最终 value 为 1、3、4，总和 8。"
            f"模型输出 `{_short_text(actual)}`，说明它漏做了删除 b、错误更新 a，或没有按顺序使用最新映射值。"
        ),
    }
    if case_id in derivations:
        return (
            f"模型最终答案 `{_short_text(actual)}` 与标准答案 `{_short_text(expected)}` 不一致。"
            + derivations[case_id]
        )
    return None


def _known_text_rule_root_cause(record: dict[str, Any]) -> str | None:
    case_id = str(record.get("case_id") or "")
    details = record.get("score", {}).get("details") or {}
    output = str(record.get("output") or "").strip()
    missing = [str(item) for item in (details.get("missing") or [])]
    missing_any = details.get("missing_any") or []

    if case_id == "challenge-rag-001":
        return (
            "问题问的是“为什么 v0.2 不把 LLM-as-judge 作为默认判分”。资料 B 给出的关键依据是：开放中文写作题只做少量规则校验和人工抽检。"
            f"模型回答 `{_short_text(output)}` 只是复述“不会默认使用”或说资料未说明，没有说出替代判分方式里的“人工抽检”，因此缺少真正解释原因的证据链。"
        )

    if case_id in {"challenge-rag-004", "challenge-rag-009", "challenge-rag-016"}:
        missing_text = "、".join(missing) if missing else "资料缺失依据"
        return (
            f"模型结论 `{_short_text(output)}` 方向正确，但回答过短，只给了“不能”而没有说明依据。"
            f"这类 RAG 题要求同时回答结论和资料中的缺失字段；本题缺少 `{missing_text}`，"
            "所以读者无法复查模型为什么不能判断。"
        )

    if case_id == "challenge-rag-017":
        return (
            "模型大体知道旧版本和 ability4096 不展示，但把关键版本号 `v0.2-challenge50` 抄成了 `v0.-challenge50`，"
            "导致缺失必需证据；同时又说资料无法判断“是否应该展示旧版本”，比题目要求的当前展示规则回答得更发散。"
            "根因是 RAG 细节复制错误加过度保守解释。"
        )

    if case_id == "challenge-rag-014" and not output:
        return (
            "题目问当前总览页对应的 token limit，资料 B/C 都指向 `ability16384`，应回答 16384。"
            "模型返回了空字符串，导致关键数字完全缺失。根因是正常 stop 但未产出正文，不是资料检索歧义。"
        )

    if missing or missing_any:
        missing_parts = []
        if missing:
            missing_parts.append("必须出现的关键信息：" + "、".join(missing))
        if missing_any:
            groups = [" / ".join(str(option) for option in group) for group in missing_any]
            missing_parts.append("每组至少一个依据表达：" + "；".join(groups))
        return (
            "模型回答没有覆盖评分规则要求的完整证据链。"
            + "；".join(missing_parts)
            + "。这通常表示答案方向可能对，但没有把资料依据说清楚。"
        )

    return None


def _degenerate_output_explanation(record: dict[str, Any]) -> str:
    case_id = str(record.get("case_id") or "")
    finish_reason = record.get("finish_reason")
    if case_id == "challenge-reasoning-015":
        return (
            "这道集合题本身很短，正确答案是 3，但模型没有给出数字，而是输出了大量跨语言碎片、内部样式词和伪代码片段，"
            f"直到 finish_reason=`{_short_text(str(finish_reason))}`。根因是生成阶段退化/失控，不是集合操作推理失败。"
        )
    return (
        "模型输出包含大量无意义重复片段或内部标记，无法作为题目答案解析。"
        f"finish_reason=`{_short_text(str(finish_reason))}`，说明失败发生在答案生成稳定性层面，而非当前 scorer 过严。"
    )


def _exact_failure_type(record: dict[str, Any]) -> str:
    expected, actual = _exact_answer_pair(record)
    if not expected:
        return "answer_mismatch"
    if _answer_repeat_count(actual, expected) > 1:
        return "duplicate_answer"
    if _looks_like_format_violation(actual, expected):
        return "format_violation"
    return "answer_mismatch"


def _exact_answer_pair(record: dict[str, Any]) -> tuple[str, str]:
    score = record.get("score") or {}
    details = score.get("details") or {}
    expected_data = record.get("expected") or {}
    expected = details.get("expected")
    if expected is None and isinstance(expected_data, dict):
        expected = expected_data.get("answer")
    actual = details.get("actual")
    if actual is None:
        actual = record.get("output")
    return str(expected or ""), str(actual or "")


def _answer_repeat_count(actual: str, expected: str) -> int:
    actual_compact = _compact_exact_text(actual)
    expected_compact = _compact_exact_text(expected)
    if not actual_compact or not expected_compact:
        return 0
    if len(actual_compact) % len(expected_compact) != 0:
        return 0
    count = len(actual_compact) // len(expected_compact)
    if count <= 1:
        return 0
    return count if actual_compact == expected_compact * count else 0


def _looks_like_format_violation(actual: str, expected: str) -> bool:
    actual_plain = _strip_common_answer_formatting(actual)
    expected_plain = _strip_common_answer_formatting(expected)
    if _normalize_exact_text(actual_plain) == _normalize_exact_text(expected_plain):
        return actual.strip() != expected.strip()
    if expected_plain and _ends_with_formatted_answer(actual, expected_plain):
        return True
    if not expected_plain or not actual_plain.startswith(expected_plain):
        return False
    rest = actual_plain[len(expected_plain) :]
    if not rest:
        return False
    return rest[0].isspace() or rest[0] in "。！？.!?,，:：;；、-"


def _strip_common_answer_formatting(value: str) -> str:
    text = str(value).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip().strip("`")
    return text.replace("*", "").strip()


def _ends_with_formatted_answer(actual: str, expected: str) -> bool:
    actual_text = str(actual).strip()
    expected_text = re.escape(str(expected).strip())
    if not expected_text:
        return False
    return re.search(rf"(?:^|\n)\s*(?:\*\*)?{expected_text}(?:\*\*)?\s*$", actual_text) is not None


def _normalize_exact_text(value: str) -> str:
    text = _strip_common_answer_formatting(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n。！？.!?,，`")


def _compact_exact_text(value: str) -> str:
    text = _strip_common_answer_formatting(value).lower()
    return re.sub(r"[\s`*_。！？.!?,，:：;；、\"'“”‘’（）()\[\]{}<>《》-]+", "", text)


def _looks_like_degenerate_output(value: str) -> bool:
    text = str(value)
    if not text:
        return False
    marker_count = (
        text.count("</think>")
        + text.count("</arg_value>")
        + text.count("<arg_value>")
        + text.count("_launcher")
        + text.count("_docs")
        + text.count("_FS")
    )
    if marker_count >= 8:
        return True
    if len(text) > 2000 and marker_count >= 3:
        return True
    return False


def _json_sequence_values(value: str) -> list[Any]:
    values, complete = _decode_json_sequence(_strip_json_markdown(value))
    return values if complete else []


def _decode_json_sequence(text: str) -> tuple[list[Any], bool]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return values, True
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return values, False
        values.append(value)
        index = end
    return values, True


def _strip_json_markdown(value: str) -> str:
    text = str(value).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _json_values_equal(left: Any, right: Any) -> bool:
    return json.dumps(left, ensure_ascii=False, sort_keys=True) == json.dumps(right, ensure_ascii=False, sort_keys=True)


def _json_sequence_schema_validity(record: dict[str, Any]) -> str:
    expected = record.get("expected") or {}
    if not isinstance(expected, dict):
        return "unknown"
    schema = expected.get("schema")
    if not isinstance(schema, dict):
        return "unknown"
    values = _json_sequence_values(str(record.get("output") or ""))
    if not values:
        return "unknown"
    invalid = [value for value in values if validate_json_schema_lite(value, schema)]
    if not invalid:
        return "all_valid"
    if len(invalid) == len(values):
        return "all_invalid"
    return "partially_valid"


def _regex_miss_explanation(record: dict[str, Any]) -> str:
    details = (record.get("score") or {}).get("details") or {}
    expected = record.get("expected") or {}
    pattern = details.get("pattern")
    if pattern is None and isinstance(expected, dict):
        pattern = expected.get("pattern")
    output = str(record.get("output") or "").strip()
    return (
        f"当前 regex scorer 要求模型输出中出现可匹配 `{_short_text(str(pattern or 'n/a'))}` 的片段，"
        f"但实际输出没有命中。模型输出片段是 `{_short_text(output)}`。"
        "这类失败通常不是“答案全错”这么粗糙，而是最后要求的固定 `FIX:` 行、函数签名或代码片段没有按标准形式写出来；"
        "需要看具体 case 判断是等价修复未被 regex 覆盖，还是模型确实少写了关键代码。"
    )


def _contains_any_miss_explanation(record: dict[str, Any]) -> str:
    expected = record.get("expected") or {}
    answers = expected.get("answers") if isinstance(expected, dict) else None
    answer_preview = "；".join(str(answer) for answer in (answers or [])[:3]) or "n/a"
    output = str(record.get("output") or "").strip()
    return (
        "当前 contains_any scorer 要求输出中逐字包含至少一个可接受短语，"
        f"例如 `{_short_text(answer_preview)}`；模型输出片段为 `{_short_text(output)}`，没有逐字命中这些短语。"
        "这说明失败点在关键短语/最终短答案没有按标准表达落地；如果正文语义已经正确，应扩充 accepted answers 或改用更结构化的 scorer。"
    )


def _generic_scorer_miss_explanation(record: dict[str, Any], failure_type: str) -> str:
    scorer = str(record.get("scorer") or "unknown")
    details = (record.get("score") or {}).get("details") or {}
    detail_text = json.dumps(details, ensure_ascii=False, sort_keys=True)
    output = str(record.get("output") or "").strip()
    return (
        f"当前失败类型是 `{failure_type}`，scorer 是 `{scorer}`。"
        f"可见判分信号为 `{_short_text(detail_text)}`，模型输出片段为 `{_short_text(output)}`。"
        "报告模板还没有这个组合的专项诊断，因此这里先给出可复查的失败信号；后续应为该 case 补一条 case-aware root cause。"
    )


def _short_text(value: str, limit: int = 120) -> str:
    text = str(value).replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _run_elapsed_ms(records: list[dict[str, Any]]) -> int | None:
    starts: list[datetime] = []
    ends: list[datetime] = []
    latencies: list[int] = []

    for record in records:
        latency = _int_or_none(record.get("latency_ms"))
        if latency is not None:
            latencies.append(latency)

        started_at = _parse_datetime(record.get("started_at"))
        if started_at is None:
            continue

        starts.append(started_at)
        ends.append(started_at + timedelta(milliseconds=latency or 0))

    if starts and ends:
        return max(0, int((max(ends) - min(starts)).total_seconds() * 1000))
    if latencies:
        return sum(latencies)
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_duration(milliseconds: object) -> str:
    value = _int_or_none(milliseconds)
    if value is None:
        return "n/a"

    total_seconds = max(0, int(round(value / 1000)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _avg(values: list[int | float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _usage_summary(records: list[dict[str, Any]]) -> dict[str, int | float]:
    summary: dict[str, int | float] = {
        "cost": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
    }
    for record in records:
        usage = record.get("usage") or {}
        summary["cost"] = float(summary["cost"]) + float(usage.get("cost") or 0)
        summary["prompt_tokens"] = int(summary["prompt_tokens"]) + int(usage.get("prompt_tokens") or 0)
        summary["completion_tokens"] = int(summary["completion_tokens"]) + int(usage.get("completion_tokens") or 0)
        completion_details = usage.get("completion_tokens_details") or {}
        summary["reasoning_tokens"] = int(summary["reasoning_tokens"]) + int(
            completion_details.get("reasoning_tokens") or 0
        )
    return summary


def _percent(value: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{value / total * 100:.1f}%"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)
