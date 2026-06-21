from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from .automation.playwright_runner import BrowserConfig, PlaywrightReportRunner
from .exports import iter_export_files, summarize_export
from .knowledge import load_knowledge
from .llm import OpenAIInterpreter, preview_interpreter_prompt
from .planner import plan_question, plan_to_dict


def _cmd_plan(args: argparse.Namespace) -> int:
    plan = plan_question(args.question, load_knowledge(args.knowledge) if args.knowledge else None)
    print(json.dumps(plan_to_dict(plan), indent=2))
    return 0


def _cmd_reports(args: argparse.Namespace) -> int:
    km = load_knowledge(args.knowledge) if args.knowledge else load_knowledge()
    payload = [
        {
            "id": report.id,
            "name": report.name,
            "tab": report.tab,
            "source_type": report.source_type,
            "columns": [column.name for column in report.columns],
        }
        for report in km.reports
    ]
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_inspect_assets(args: argparse.Namespace) -> int:
    root = Path(args.path)
    summaries = []
    for path in iter_export_files(root):
        summary = summarize_export(path)
        item = asdict(summary)
        item["path"] = str(path.relative_to(root))
        summaries.append(item)
    if args.json:
        print(json.dumps(summaries, indent=2, default=str))
    else:
        for summary in summaries:
            print(summary["path"])
            if summary.get("error"):
                print(f"  error: {summary['error']}")
                continue
            for sheet in summary["sheets"]:
                print(f"  {sheet['name']}: {len(sheet['columns'])} columns")
    return 0


def _cmd_ai_plan(args: argparse.Namespace) -> int:
    result = OpenAIInterpreter().interpret(args.question)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_prompt_preview(args: argparse.Namespace) -> int:
    result = preview_interpreter_prompt(args.question)
    print(json.dumps(result, indent=2))
    return 0


async def _login_session(args: argparse.Namespace) -> None:
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    async with PlaywrightReportRunner(config) as runner:
        page = await runner.new_page()
        await runner.login(page)
        if args.storage_state:
            await runner.save_storage_state(Path(args.storage_state))


def _cmd_login_session(args: argparse.Namespace) -> int:
    asyncio.run(_login_session(args))
    print("RT BDI login succeeded")
    if args.storage_state:
        print(f"Saved browser storage state to {args.storage_state}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtbdi")
    subparsers = parser.add_subparsers(required=True)

    plan = subparsers.add_parser("plan", help="Plan a plain-English RT BDI question")
    plan.add_argument("question")
    plan.add_argument("--knowledge")
    plan.set_defaults(func=_cmd_plan)

    reports = subparsers.add_parser("reports", help="List reports in the knowledge map")
    reports.add_argument("--knowledge")
    reports.set_defaults(func=_cmd_reports)

    inspect = subparsers.add_parser("inspect-assets", help="Summarize spreadsheet exports under a folder")
    inspect.add_argument("path")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=_cmd_inspect_assets)

    ai_plan = subparsers.add_parser("ai-plan", help="Use OpenAI to refine a report plan")
    ai_plan.add_argument("question")
    ai_plan.set_defaults(func=_cmd_ai_plan)

    prompt = subparsers.add_parser("prompt-preview", help="Preview the OpenAI planning prompt without calling the API")
    prompt.add_argument("question")
    prompt.set_defaults(func=_cmd_prompt_preview)

    login = subparsers.add_parser("login-session", help="Log into RT BDI and optionally save a browser storage state")
    login.add_argument("--headful", action="store_true", help="Show the browser while logging in")
    login.add_argument("--storage-state", help="Path to save Playwright storage state JSON")
    login.add_argument("--downloads-dir", default="downloads")
    login.set_defaults(func=_cmd_login_session)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
