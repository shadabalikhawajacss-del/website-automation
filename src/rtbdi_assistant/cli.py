from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from .answers import answer_from_exports
from .automation.playwright_runner import BrowserConfig, PlaywrightReportRunner
from .exports import iter_export_files, summarize_export
from .home import answer_home_question, extract_home_snapshot
from .intent import ConversationMemory, select_live_reports
from .knowledge import load_knowledge
from .llm import OpenAIInterpreter, preview_interpreter_prompt, select_live_intent
from .models import DateRange
from .planner import plan_question, plan_to_dict

GRID_EXPORT_REPORTS = {"finance_report", "trade_in_custom_report"}
EXPORT_BUTTON_REPORTS = {"activation_mrc_by_employee"}
FORM_POST_EXPORT_REPORTS = {"bill_payment_listing"}
HTML_TABLE_FALLBACK_REPORTS = {
    "promo_fee_report",
    "esn_change_report",
    "inventory_transaction_report",
    "not_verified_serial_report",
    "tangible_adjusted_report",
}


async def _download_or_fallback_export(runner: PlaywrightReportRunner, page, report_id: str) -> Path:
    if report_id in FORM_POST_EXPORT_REPORTS:
        return await runner.post_form_export(
            page,
            field_overrides={"frmMarketID": "HOUSTON", "frmStateID": "TX", "btnExcel": "Export to Excel"},
            fallback_filename=f"{report_id}.csv",
        )
    if report_id in HTML_TABLE_FALLBACK_REPORTS:
        return await runner.save_visible_tables(page, f"{report_id}.html")
    try:
        return await runner.download_export(
            page,
            prefer_grid_export=report_id in GRID_EXPORT_REPORTS,
            prefer_export_button=report_id in EXPORT_BUTTON_REPORTS,
        )
    except Exception:
        if report_id not in HTML_TABLE_FALLBACK_REPORTS:
            raise
        return await runner.save_visible_tables(page, f"{report_id}.html")


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


async def _home_snapshot(args: argparse.Namespace) -> dict[str, object]:
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    async with PlaywrightReportRunner(config) as runner:
        page = await runner.new_page()
        if not config.storage_state:
            await runner.login(page)
        await page.goto(config.base_url, wait_until="domcontentloaded")
        if not await page.get_by_text("LOGOUT", exact=False).count():
            await runner.login(page)
        snapshot = await extract_home_snapshot(page)
        return asdict(snapshot)


async def _download_home_snapshot(args: argparse.Namespace):
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    async with PlaywrightReportRunner(config) as runner:
        page = await runner.new_page()
        if not config.storage_state:
            await runner.login(page)
        await page.goto(config.base_url, wait_until="domcontentloaded")
        return await extract_home_snapshot(page)


def _cmd_live_home(args: argparse.Namespace) -> int:
    print(json.dumps(asyncio.run(_home_snapshot(args)), indent=2))
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
        await runner.generate(page, required=False)
        return await _download_or_fallback_export(runner, page, report.id)


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
        await runner.generate(page, required=False)
        return await _download_or_fallback_export(runner, page, report_id)


def _cmd_live_export(args: argparse.Namespace) -> int:
    path = asyncio.run(_live_export(args))
    summary = summarize_export(path)
    payload = asdict(summary)
    payload["path"] = str(path)
    print(json.dumps(payload, indent=2, default=str))
    return 0


async def _live_answer(args: argparse.Namespace) -> dict[str, object]:
    memory = ConversationMemory.load(Path(args.memory) if args.memory else None)
    intent = select_live_intent(args.question, memory)
    if intent.needs_clarification:
        return {
            "answer": intent.needs_clarification,
            "reports_used": [],
            "canonical_question": intent.canonical_question,
            "memory_used": intent.memory_used,
            "date_range": {},
            "rows_used": 0,
            "notes": [intent.reasoning] if intent.reasoning else [],
            "exports": {},
        }
    if intent.report_ids == ("home_dashboard",):
        snapshot = await _download_home_snapshot(args)
        result = answer_home_question(intent.canonical_question, snapshot)
        memory.update(result.context)
        memory_path = Path(args.memory) if args.memory else None
        memory.save(memory_path)
        return {
            "answer": result.answer,
            "reports_used": list(result.reports_used),
            "canonical_question": intent.canonical_question,
            "memory_used": intent.memory_used,
            "date_range": {
                "start": result.date_range.start.isoformat(),
                "end": result.date_range.end.isoformat(),
                "label": result.date_range.label,
            },
            "rows_used": result.rows_used,
            "notes": list(result.notes),
            "exports": {},
        }

    plan = plan_question(intent.canonical_question)
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
            "canonical_question": intent.canonical_question,
            "memory_used": intent.memory_used,
        }

    exports = {report_id: await _download_live_report(report_id, plan.date_range, args) for report_id in intent.report_ids}
    answer_question = intent.canonical_question
    if intent.original_question.casefold() not in answer_question.casefold():
        answer_question = f"{intent.canonical_question} {intent.original_question}"
    result = answer_from_exports(answer_question, exports)
    memory.update(result.context)
    memory_path = Path(args.memory) if args.memory else None
    memory.save(memory_path)
    return {
        "answer": result.answer,
        "reports_used": list(result.reports_used),
        "canonical_question": intent.canonical_question,
        "memory_used": intent.memory_used,
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


def _cmd_route_debug(args: argparse.Namespace) -> int:
    memory = ConversationMemory.load(Path(args.memory) if args.memory else None)
    intent = select_live_intent(args.question, memory)
    print(
        json.dumps(
            {
                "question": args.question,
                "canonical_question": intent.canonical_question,
                "report_ids": list(intent.report_ids),
                "reasoning": intent.reasoning,
                "confidence": intent.confidence,
                "needs_clarification": intent.needs_clarification,
                "memory_used": intent.memory_used,
            },
            indent=2,
        )
    )
    return 0


async def _validate_reports(args: argparse.Namespace) -> list[dict[str, object]]:
    km = load_knowledge(args.knowledge) if args.knowledge else load_knowledge()
    requested = [report.id for report in km.reports if report.source_type != "dashboard"] if args.all else args.report_id
    if args.limit:
        requested = requested[: args.limit]
    report_range = DateRange(date.fromisoformat(args.start), date.fromisoformat(args.end), f"{args.start} to {args.end}", explicit=True)
    config = BrowserConfig.from_env(headless=not args.headful, downloads_dir=Path(args.downloads_dir))
    results: list[dict[str, object]] = []
    async with PlaywrightReportRunner(config) as runner:
        for report_id in requested:
            report = km.get(report_id)
            result: dict[str, object] = {
                "report_id": report.id,
                "name": report.name,
                "tab": report.tab,
                "url_path": report.url_path,
                "status": "pending",
            }
            try:
                page = await runner.new_page()
                if not config.storage_state:
                    await runner.login(page)
                await runner.open_report(page, report)
                result["opened_url"] = page.url
                if "accessdenied" in page.url.casefold() or "access denied" in (await page.locator("body").inner_text()).casefold():
                    result.update({"status": "access_denied", "error": "The logged-in RT BDI user cannot access this report."})
                    await page.close()
                    results.append(result)
                    continue
                result["date_set"] = await runner.set_date_range(page, report_range, required=False)
                await runner.generate(page, required=False)
                path = await _download_or_fallback_export(runner, page, report.id)
                summary = summarize_export(path)
                result.update(
                    {
                        "status": "downloaded_parse_failed" if summary.error else "passed",
                        "download_path": str(path),
                        "kind": summary.kind,
                        "sheets": [asdict(sheet) for sheet in summary.sheets],
                        "error": summary.error,
                    }
                )
                await page.close()
            except Exception as exc:
                status = "no_data" if "No generated HTML tables were available" in str(exc) else "failed"
                result.update({"status": status, "error": f"{type(exc).__name__}: {exc}"})
                if not args.continue_on_error:
                    results.append(result)
                    return results
            results.append(result)
    return results


def _cmd_validate_reports(args: argparse.Namespace) -> int:
    results = asyncio.run(_validate_reports(args))
    print(json.dumps(results, indent=2, default=str))
    failed = [result for result in results if result["status"] != "passed"]
    return 1 if failed and args.fail_on_error else 0


def _extract_numbered_questions(path: Path) -> list[tuple[int, str]]:
    if path.suffix.casefold() == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        text = path.read_text(encoding="utf-8")
    questions: list[tuple[int, str]] = []
    for line in text.splitlines():
        match = re.match(r"^(\d+)\.\s+(.*)", line.strip())
        if match:
            questions.append((int(match.group(1)), match.group(2).strip()))
    return questions


def _cmd_eval_question_bank(args: argparse.Namespace) -> int:
    km = load_knowledge(args.knowledge) if args.knowledge else load_knowledge()
    questions = _extract_numbered_questions(Path(args.path))
    expected_clarify = set(args.expected_clarify or [])
    results = []
    for number, question in questions:
        plan = plan_question(question, km)
        status = "passed"
        reason = "routed"
        if plan.needs_clarification:
            status = "passed" if number in expected_clarify or args.allow_clarifications else "clarified"
            reason = plan.needs_clarification
        elif number in expected_clarify:
            status = "failed"
            reason = "expected clarification but planner routed the question"
        elif not plan.report_ids:
            status = "failed"
            reason = "no report route"
        results.append(
            {
                "number": number,
                "question": question,
                "status": status,
                "reason": reason,
                "reports": list(plan.report_ids),
                "metrics": [asdict(metric) for metric in plan.metrics],
                "date_range": {
                    "start": plan.date_range.start.isoformat(),
                    "end": plan.date_range.end.isoformat(),
                    "label": plan.date_range.label,
                },
            }
        )
    payload = {
        "total": len(results),
        "passed": sum(1 for result in results if result["status"] == "passed"),
        "failed": sum(1 for result in results if result["status"] == "failed"),
        "clarified": sum(1 for result in results if result["status"] == "clarified"),
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 1 if payload["failed"] else 0


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

    home = subparsers.add_parser("live-home", help="Extract the live Home dashboard snapshot")
    home.add_argument("--headful", action="store_true", help="Show the browser while running")
    home.add_argument("--downloads-dir", default="downloads")
    home.set_defaults(func=_cmd_live_home)

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
    live_answer.add_argument("--memory", default=".rtbdi-memory.json", help="Conversation memory JSON path for follow-up questions")
    live_answer.set_defaults(func=_cmd_live_answer)

    route_debug = subparsers.add_parser("route-debug", help="Show how a question routes before running live reports")
    route_debug.add_argument("question")
    route_debug.add_argument("--memory", default=".rtbdi-memory.json")
    route_debug.set_defaults(func=_cmd_route_debug)

    validate = subparsers.add_parser("validate-reports", help="Open/generate/export mapped live reports and summarize results")
    validate.add_argument("report_id", nargs="*", help="Report ids to validate")
    validate.add_argument("--all", action="store_true", help="Validate every non-dashboard report in the knowledge map")
    validate.add_argument("--start", required=True, help="Inclusive start date, YYYY-MM-DD")
    validate.add_argument("--end", required=True, help="Inclusive end date, YYYY-MM-DD")
    validate.add_argument("--knowledge")
    validate.add_argument("--headful", action="store_true", help="Show the browser while running")
    validate.add_argument("--downloads-dir", default="downloads/validation")
    validate.add_argument("--continue-on-error", action="store_true")
    validate.add_argument("--fail-on-error", action="store_true")
    validate.add_argument("--limit", type=int)
    validate.set_defaults(func=_cmd_validate_reports)

    qbank = subparsers.add_parser("eval-question-bank", help="Evaluate a numbered question bank PDF/text file against the planner")
    qbank.add_argument("path")
    qbank.add_argument("--knowledge")
    qbank.add_argument("--allow-clarifications", action="store_true")
    qbank.add_argument("--expected-clarify", type=int, nargs="*", default=[109, 110, 111, 112, 113, 114])
    qbank.set_defaults(func=_cmd_eval_question_bank)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
