from __future__ import annotations

import shutil
from pathlib import Path

from dracobench.report import select_preferred_run_paths


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
REPORTS_DIR = ROOT / "reports"
RUNS_DIR = ROOT / "runs"


def main() -> None:
    _reset_dir(PUBLIC_DIR)
    _copy_report_index()
    _copy_selected_results()
    _write_root_redirect()


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_report_index() -> None:
    _copy_file(REPORTS_DIR / "index.html", PUBLIC_DIR / "reports" / "index.html")


def _copy_selected_results() -> None:
    run_paths = [
        path
        for path in sorted(RUNS_DIR.glob("v0.3-challenge100-*-ability16384*.jsonl"))
        if "retry429" not in path.name
    ]
    for run_path in select_preferred_run_paths(run_paths):
        _copy_file(run_path, PUBLIC_DIR / "runs" / run_path.name)
        report_path = REPORTS_DIR / f"{run_path.stem}.html"
        if report_path.exists():
            _copy_file(report_path, PUBLIC_DIR / "reports" / report_path.name)
            _copy_file(report_path, PUBLIC_DIR / report_path.name)


def _write_root_redirect() -> None:
    index_path = PUBLIC_DIR / "index.html"
    index_path.write_text(
        """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=/reports/index.html">
  <title>DracoBench Results</title>
</head>
<body>
  <a href="/reports/index.html">DracoBench Results</a>
</body>
</html>
""",
        encoding="utf-8",
    )


def _copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


if __name__ == "__main__":
    main()
