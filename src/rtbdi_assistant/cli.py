from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .answers import answer_from_exports
from .automation.playwright_runner import BrowserConfig, PlaywrightReportRunner
from .exports import iter_export_files, summarize_export
from .knowledge import load_knowledge
from .llm import OpenAIInterpreter, preview_interpreter_prompt
from .models import DateRange
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


async def _live_export(args: argparse.Namespace) -> Path:
    km = load_knowledge(args.knowledge) if args.knowledge else load_knowledge()
    report = km.get(args.report_id)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise SystemExit("--start must be on or before --end")
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    async with PlaywrightReportRunner(config) as runner:
        page = await runner.new_page()
        if not config.storage_state:
            await runner.login(page)
        await runner.open_report(page, report)
        await runner.set_date_range(page, DateRange(start, end, f"{start.isoformat()} to {end.isoformat()}", explicit=True), required=False)
        await runner.generate(page)
        return await runner.download_export(page, prefer_grid_export=report.id in {"finance_report", "trade_in_custom_report"})


async def _download_live_report(report_id: str, report_range: DateRange, args: argparse.Namespace) -> Path:
    km = load_knowledge(args.knowledge) if getattr(args, "knowledge", None) else load_knowledge()
    report = km.get(report_id)
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    async with PlaywrightReportRunner(config) as runner:
        page = await runner.new_page()
        if not config.storage_state:
            await runner.login(page)
        await runner.open_report(page, report)
        await runner.set_date_range(page, report_range, required=False)
        await runner.generate(page)
        return await runner.download_export(page, prefer_grid_export=report_id in {"finance_report", "trade_in_custom_report"})


def _cmd_live_export(args: argparse.Namespace) -> int:
    path = asyncio.run(_live_export(args))
    summary = summarize_export(path)
    payload = asdict(summary)
    payload["path"] = str(path)
    print(json.dumps(payload, indent=2, default=str))
    return 0


async def _live_answer(args: argparse.Namespace) -> dict[str, object]:
    plan = plan_question(args.question)
    if plan.needs_clarification:
        return {
            "answer": plan.needs_clarification,
            "reports_used": [],
            "date_range": {
                "start": plan.date_range.start.isoformat(),
                "end": plan.date_range.end.isoformat(),
                "label": plan.date_range.label,
            },
            "rows_used": 0,
            "notes": list(plan.notes),
        }

    lowered = args.question.casefold()
    if "plan mix" in lowered and "inventory" in lowered and ("gross profit" in lowered or "#2" in lowered or "number 2" in lowered):
        report_ids = ("employee_ranking_by_box_sales", "employee_mrc_matrix_report", "kpi_report_by_employee", "inventory_report")
    elif "finance" in lowered and ("gross profit" in lowered or "gp" in lowered):
        report_ids = ("finance_report", "kpi_report_by_employee")
    elif "accessor" in lowered and ("gross profit" in lowered or "store" in lowered) and ("top" in lowered or "seller" in lowered or "most" in lowered):
        report_ids = ("employee_ranking_by_box_sales", "kpi_report_by_employee")
    elif "trade" in lowered or "carrier" in lowered or "make and model" in lowered:
        report_ids = ("trade_in_custom_report",)
    elif "finance" in lowered or "financed" in lowered or "approved amount" in lowered:
        report_ids = ("finance_report",)
    elif "slow mover" in lowered or "sold in the last" in lowered or "sold in last" in lowered or "fastest-selling" in lowered or "30-day" in lowered or "7-day" in lowered or "a16" in lowered or "revvl" in lowered:
        report_ids = ("phone_trend_by_market",)
    elif "purchase order" in lowered or "open po" in lowered or ("po" in lowered and "top" not in lowered):
        report_ids = ("po_listing_report",)
    elif "transfer" in lowered:
        report_ids = ("inventory_transfer_listing",)
    elif "audit" in lowered or "variance" in lowered or "unmatched" in lowered:
        report_ids = ("inventory_tangible_audit_log",) if "tangible" in lowered or "variance" in lowered else ("inventory_audit_log",)
    elif "inventory" in lowered or "stock" in lowered or "on hand" in lowered or "apple" in lowered or "samsung" in lowered or "motorola" in lowered or "serialized" in lowered:
        report_ids = ("inventory_report",)
    elif ("top" in lowered or "rank" in lowered or "most" in lowered or "bottom" in lowered) and "gross profit" in lowered:
        report_ids = ("kpi_report_by_employee",)
    elif "store" in lowered and ("top" in lowered or "rank" in lowered or "most" in lowered or "worst" in lowered):
        report_ids = ("employee_performance_report",)
    elif ("top" in lowered or "rank" in lowered or "most" in lowered or "bottom" in lowered) and ("accessor" in lowered or "activation" in lowered or "boxes" in lowered or "phones" in lowered):
        report_ids = ("employee_ranking_by_box_sales",)
    elif "conversion" in lowered or "ratio" in lowered or "qpay" in lowered:
        report_ids = ("employee_conversion_ratio",)
    else:
        report_ids = ("employee_performance_report",)

    exports = {report_id: await _download_live_report(report_id, plan.date_range, args) for report_id in report_ids}
    result = answer_from_exports(args.question, exports)
    return {
        "answer": result.answer,
        "reports_used": list(result.reports_used),
        "date_range": {
            "start": result.date_range.start.isoformat(),
            "end": result.date_range.end.isoformat(),
            "label": result.date_range.label,
        },
        "rows_used": result.rows_used,
        "notes": list(result.notes),
        "exports": {report_id: str(path) for report_id, path in exports.items()},
    }


def _cmd_live_answer(args: argparse.Namespace) -> int:
    print(json.dumps(asyncio.run(_live_answer(args)), indent=2))
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

    live_export = subparsers.add_parser("live-export", help="Generate a live RT BDI report and download its export")
    live_export.add_argument("report_id", help="Report id from knowledge/report_map.json")
    live_export.add_argument("--start", required=True, help="Inclusive start date, YYYY-MM-DD")
    live_export.add_argument("--end", required=True, help="Inclusive end date, YYYY-MM-DD")
    live_export.add_argument("--knowledge")
    live_export.add_argument("--headful", action="store_true", help="Show the browser while running")
    live_export.add_argument("--downloads-dir", default="downloads")
    live_export.set_defaults(func=_cmd_live_export)

    live_answer = subparsers.add_parser("live-answer", help="Answer a supported question using live RT BDI exports")
    live_answer.add_argument("question")
    live_answer.add_argument("--knowledge")
    live_answer.add_argument("--headful", action="store_true", help="Show the browser while running")
    live_answer.add_argument("--downloads-dir", default="downloads")
    live_answer.set_defaults(func=_cmd_live_answer)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
