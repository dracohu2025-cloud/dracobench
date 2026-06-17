from __future__ import annotations

import html
import json
from collections import Counter

from .models import Case


def build_review_html(cases: list[Case], title: str = "DracoBench Case Review") -> str:
    suite_counts = Counter(case.suite for case in cases)
    suite_buttons = "\n".join(
        f'<button class="filter" type="button" data-filter="{_escape(suite)}">{_escape(suite)} <span>{count}</span></button>'
        for suite, count in sorted(suite_counts.items())
    )
    case_items = "\n".join(_render_case(case, index) for index, case in enumerate(cases, start=1))

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
      --ink: #171512;
      --muted: #625d52;
      --line: #d8d0c0;
      --panel: #fffaf0;
      --teal: #007f7a;
      --red: #b23a48;
      --blue: #2b5c9e;
      --amber: #9a6500;
      --shadow: 0 12px 36px rgba(26, 20, 12, 0.10);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background:
        linear-gradient(90deg, rgba(23, 21, 18, 0.035) 1px, transparent 1px),
        linear-gradient(180deg, rgba(23, 21, 18, 0.035) 1px, transparent 1px),
        var(--paper);
      background-size: 32px 32px;
      color: var(--ink);
      font-family: "Avenir Next", "Noto Sans SC", "Source Han Sans SC", sans-serif;
      line-height: 1.55;
    }}

    header {{
      border-bottom: 1px solid var(--line);
      background: rgba(247, 243, 234, 0.92);
      backdrop-filter: blur(14px);
      position: sticky;
      top: 0;
      z-index: 2;
    }}

    .topbar {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 22px 24px 18px;
    }}

    h1 {{
      margin: 0 0 14px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 34px;
      line-height: 1.05;
      letter-spacing: 0;
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }}

    .pill {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 4px 8px;
      border-radius: 999px;
      color: var(--ink);
    }}

    .controls {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px 24px 22px;
      display: grid;
      grid-template-columns: minmax(220px, 360px) 1fr;
      gap: 14px;
      align-items: start;
    }}

    input[type="search"] {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      outline-color: var(--teal);
    }}

    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    button.filter {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
      cursor: pointer;
    }}

    button.filter.active {{
      background: var(--ink);
      color: var(--paper);
      border-color: var(--ink);
    }}

    button.filter span {{
      color: var(--amber);
      margin-left: 4px;
    }}

    button.filter.active span {{
      color: #ffd27a;
    }}

    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}

    .case {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 250, 240, 0.94);
      box-shadow: var(--shadow);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 16px;
    }}

    .case.hidden {{
      display: none;
    }}

    .case-index {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 32px;
      color: var(--red);
      line-height: 1;
      margin-bottom: 12px;
    }}

    .case-id {{
      font-weight: 700;
      overflow-wrap: anywhere;
    }}

    .case-suite {{
      display: inline-block;
      margin: 10px 0;
      color: var(--teal);
      font-weight: 700;
    }}

    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}

    .tag {{
      border-left: 3px solid var(--blue);
      background: #eef3f4;
      padding: 2px 6px;
      font-size: 12px;
      color: #263b42;
    }}

    .prompt {{
      white-space: pre-wrap;
      font-size: 16px;
      margin: 0 0 14px;
    }}

    .scorer {{
      display: grid;
      grid-template-columns: minmax(120px, 180px) 1fr;
      gap: 10px;
      align-items: start;
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }}

    .label {{
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
    }}

    code, pre {{
      font-family: "SF Mono", "Cascadia Code", "Menlo", monospace;
    }}

    pre {{
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #1e1c19;
      color: #f8ead0;
      border-radius: 8px;
      padding: 12px;
      max-height: 320px;
      overflow: auto;
    }}

    @media (max-width: 820px) {{
      .controls {{
        grid-template-columns: 1fr;
      }}

      .case {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <h1>{_escape(title)}</h1>
      <div class="meta">
        <span class="pill">{len(cases)} cases</span>
        <span class="pill">{len(suite_counts)} suites</span>
        <span>DracoBench case review</span>
      </div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search id, suite, prompt, tags">
      <div class="filters">
        <button class="filter active" type="button" data-filter="all">all <span>{len(cases)}</span></button>
        {suite_buttons}
      </div>
    </div>
  </header>
  <main id="cases">
    {case_items}
  </main>
  <script>
    const search = document.querySelector('#search');
    const filters = [...document.querySelectorAll('.filter')];
    const cases = [...document.querySelectorAll('.case')];
    let activeSuite = 'all';

    function applyFilters() {{
      const query = search.value.trim().toLowerCase();
      for (const item of cases) {{
        const suiteOk = activeSuite === 'all' || item.dataset.suite === activeSuite;
        const textOk = !query || item.textContent.toLowerCase().includes(query);
        item.classList.toggle('hidden', !(suiteOk && textOk));
      }}
    }}

    search.addEventListener('input', applyFilters);
    filters.forEach((button) => {{
      button.addEventListener('click', () => {{
        filters.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        activeSuite = button.dataset.filter;
        applyFilters();
      }});
    }});
  </script>
</body>
</html>
"""


def _render_case(case: Case, index: int) -> str:
    tags = "".join(f'<span class="tag">{_escape(tag)}</span>' for tag in case.tags)
    expected = json.dumps(case.expected, ensure_ascii=False, indent=2)
    searchable = " ".join([case.id, case.suite, case.scorer, case.prompt, " ".join(case.tags)])
    return f"""<article class="case" data-suite="{_escape(case.suite)}" data-search="{_escape(searchable)}">
  <aside>
    <div class="case-index">{index:02d}</div>
    <div class="case-id">{_escape(case.id)}</div>
    <div class="case-suite">{_escape(case.suite)}</div>
    <div class="tags">{tags}</div>
  </aside>
  <section>
    <p class="prompt">{_escape(case.prompt)}</p>
    <div class="scorer">
      <div class="label">Scorer</div>
      <code>{_escape(case.scorer)}</code>
      <div class="label">Expected</div>
      <pre>{_escape(expected)}</pre>
    </div>
  </section>
</article>"""


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)
