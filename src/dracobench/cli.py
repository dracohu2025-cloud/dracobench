from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .cases import filter_cases, load_cases
from .report import write_html_report, write_index_report, write_markdown_report
from .review import build_review_html
from .runner import run_cases


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dracobench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate case files.")
    validate_parser.add_argument("--cases", required=True)

    list_parser = subparsers.add_parser("list", help="List cases.")
    list_parser.add_argument("--cases", required=True)
    list_parser.add_argument("--suite", action="append", default=[])
    list_parser.add_argument("--limit", type=int)

    run_parser = subparsers.add_parser("run", help="Run benchmark cases through a model backend.")
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--cases", required=True)
    run_parser.add_argument("--backend", choices=["openrouter", "volcengine-ark"], default="openrouter")
    run_parser.add_argument("--suite", action="append", default=[])
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--out")
    run_parser.add_argument("--report")
    run_parser.add_argument("--html-report")
    run_parser.add_argument("--temperature", type=float, default=0)
    run_parser.add_argument("--max-tokens", type=int, default=1024)
    run_parser.add_argument("--seed", type=int)
    run_parser.add_argument("--sleep", type=float, default=0)
    run_parser.add_argument("--provider-only", help="Comma-separated OpenRouter provider slugs.")
    run_parser.add_argument("--provider-order", help="Comma-separated OpenRouter provider slugs.")
    run_parser.add_argument("--provider-sort", choices=["price", "throughput", "latency"])
    run_parser.add_argument("--no-fallbacks", action="store_true")
    run_parser.add_argument("--data-collection", choices=["allow", "deny"])

    report_parser = subparsers.add_parser("report", help="Build a Markdown report from a run JSONL file.")
    report_parser.add_argument("--run", required=True)
    report_parser.add_argument("--out", required=True)

    report_html_parser = subparsers.add_parser("report-html", help="Build an HTML report from a run JSONL file.")
    report_html_parser.add_argument("--run", required=True)
    report_html_parser.add_argument("--out", required=True)
    report_html_parser.add_argument("--title", default="DracoBench Report")

    review_parser = subparsers.add_parser("review-html", help="Build a static HTML page for reviewing cases.")
    review_parser.add_argument("--cases", required=True)
    review_parser.add_argument("--out", required=True)
    review_parser.add_argument("--title", default="DracoBench Case Review")

    index_parser = subparsers.add_parser("index-html", help="Build an HTML index from run JSONL files.")
    index_parser.add_argument("--runs", nargs="+", required=True)
    index_parser.add_argument("--out", required=True)
    index_parser.add_argument("--title", default="DracoBench Results Index")

    args = parser.parse_args(argv)

    if args.command == "validate":
        cases = load_cases(args.cases)
        print(f"OK: loaded {len(cases)} cases from {args.cases}")
        return

    if args.command == "list":
        cases = filter_cases(load_cases(args.cases), suites=args.suite, limit=args.limit)
        for case in cases:
            print(f"{case.id}\t{case.suite}\t{case.scorer}\t{','.join(case.tags)}")
        return

    if args.command == "run":
        cases = filter_cases(load_cases(args.cases), suites=args.suite, limit=args.limit)
        out_path = Path(args.out or default_run_path(args.model))
        report_path = Path(args.report or default_report_path(args.model))
        html_report_path = Path(args.html_report or default_html_report_path(args.model))
        provider = build_provider_config(args)
        if args.backend != "openrouter" and provider:
            raise SystemExit("provider routing options are only supported with --backend openrouter")
        records = run_cases(
            cases=cases,
            model=args.model,
            output_path=out_path,
            provider=provider,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=args.seed,
            sleep_seconds=args.sleep,
            backend=args.backend,
        )
        write_markdown_report(records, report_path)
        write_html_report(records, html_report_path, title=f"DracoBench Report: {args.model}")
        print(f"Wrote run details: {out_path}")
        print(f"Wrote report: {report_path}")
        print(f"Wrote HTML report: {html_report_path}")
        return

    if args.command == "report":
        records = load_jsonl(args.run)
        write_markdown_report(records, args.out)
        print(f"Wrote report: {args.out}")
        return

    if args.command == "report-html":
        records = load_jsonl(args.run)
        write_html_report(records, args.out, title=args.title)
        print(f"Wrote HTML report: {args.out}")
        return

    if args.command == "review-html":
        cases = load_cases(args.cases)
        html = build_review_html(cases, title=args.title)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote review HTML: {out_path}")
        return

    if args.command == "index-html":
        run_paths = expand_paths(args.runs)
        write_index_report(run_paths, args.out, title=args.title)
        print(f"Wrote index HTML: {args.out}")
        return


def build_provider_config(args: argparse.Namespace) -> dict[str, Any] | None:
    provider: dict[str, Any] = {}
    if args.provider_only:
        provider["only"] = split_csv(args.provider_only)
    if args.provider_order:
        provider["order"] = split_csv(args.provider_order)
    if args.provider_sort:
        provider["sort"] = args.provider_sort
    if args.no_fallbacks:
        provider["allow_fallbacks"] = False
    if args.data_collection:
        provider["data_collection"] = args.data_collection
    return provider or None


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def expand_paths(values: list[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        matches = sorted(glob.glob(value))
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(value))
    return paths


def default_run_path(model: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"runs/{stamp}-{slugify(model)}.jsonl"


def default_report_path(model: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"reports/{stamp}-{slugify(model)}.md"


def default_html_report_path(model: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"reports/{stamp}-{slugify(model)}.html"


def slugify(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            records.append(json.loads(line))
    return records


if __name__ == "__main__":
    main()
