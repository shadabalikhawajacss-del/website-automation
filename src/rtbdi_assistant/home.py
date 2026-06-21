from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from playwright.async_api import Page

from .answers import AnswerResult
from .models import DateRange


@dataclass(frozen=True)
class HomeSnapshot:
    url: str
    top_stores: list[dict[str, str]]
    period_summary: list[dict[str, str]]
    today_snapshot: dict[str, str]
    previous_day_rows: list[dict[str, str]]
    chart_tables: list[dict[str, Any]]


def _rows_from_table_text(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    headers = [part.strip() for part in lines[0].split("\t") if part.strip()]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = [part.strip() for part in line.split("\t")]
        if len(values) < len(headers):
            continue
        rows.append(dict(zip(headers, values[: len(headers)])))
    return rows


def _key_values_from_text(text: str) -> dict[str, str]:
    parts = [part.strip().replace("\xa0", "") for part in text.split("\t") if part.strip().replace("\xa0", "")]
    result: dict[str, str] = {}
    for idx in range(0, len(parts) - 1, 2):
        result[parts[idx].rstrip(":")] = parts[idx + 1]
    return result


async def extract_home_snapshot(page: Page) -> HomeSnapshot:
    url = page.url
    table_texts = await page.locator("table").evaluate_all(
        """tables => tables.map(t => ({id:t.id || "", text:(t.innerText || "").trim()})).filter(t => t.text)"""
    )

    top_stores: list[dict[str, str]] = []
    period_summary: list[dict[str, str]] = []
    previous_day_rows: list[dict[str, str]] = []
    today_snapshot: dict[str, str] = {}
    chart_tables: list[dict[str, Any]] = []

    for table in table_texts:
        text = table["text"]
        if "Store ID" in text and "NEW & REACT" in text:
            top_stores = _rows_from_table_text(text)
        elif "Store Count" in text and "Total Activation" in text:
            period_summary = _rows_from_table_text(text)
        elif "Total Stores" in text and "Total Activation" in text and "Total Invoices" in text:
            today_snapshot = _key_values_from_text(text)
        elif table["id"] == "BoxReport" or ("Box Cnt" in text and "MTD Tot" in text):
            previous_day_rows = _rows_from_table_text(text)
        elif "\t" in text and len(text.splitlines()) > 1:
            rows = _rows_from_table_text(text)
            if rows:
                chart_tables.append({"id": table["id"], "rows": rows})

    return HomeSnapshot(
        url=url,
        top_stores=top_stores,
        period_summary=period_summary,
        today_snapshot=today_snapshot,
        previous_day_rows=previous_day_rows,
        chart_tables=chart_tables,
    )


def _top_n_from_question(question: str, default: int = 10) -> int:
    import re

    match = re.search(r"\btop\s+(\d+)", question, flags=re.IGNORECASE)
    return int(match.group(1)) if match else default


def answer_home_question(question: str, snapshot: HomeSnapshot) -> AnswerResult:
    lowered = question.casefold()
    today = date.today()
    report_range = DateRange(today, today, "home dashboard", explicit=False)

    if "today" in lowered or "snapshot" in lowered:
        values = ", ".join(f"{key}: {value}" for key, value in snapshot.today_snapshot.items())
        return AnswerResult(
            f"Today's Home snapshot: {values}.",
            ("home_dashboard",),
            report_range,
            1 if snapshot.today_snapshot else 0,
            context={"last_metric": "today snapshot"},
        )

    if "top" in lowered and "store" in lowered:
        count = _top_n_from_question(question)
        rows = snapshot.top_stores[:count]
        lines = [
            f"{idx}. {row.get('Store Name', 'unknown')} - {row.get('PPD (Tot Act)', 'unknown')} activations, {row.get('Accessory', 'unknown')} accessory, {row.get('Qpay Conv%', 'unknown')} conversion"
            for idx, row in enumerate(rows, start=1)
        ]
        return AnswerResult(
            f"Home Top {len(rows)} stores: " + "; ".join(lines) + ".",
            ("home_dashboard",),
            report_range,
            len(rows),
            context={"last_stores": [row.get("Store Name", "") for row in rows if row.get("Store Name")], "last_metric": "home top stores"},
        )

    if "previous" in lowered or "yesterday" in lowered:
        rows = snapshot.previous_day_rows[:_top_n_from_question(question, default=10)]
        lines = [
            f"{idx}. {row.get('Store Name / Company Name', 'unknown')} - boxes {row.get('Box Cnt', 'unknown')}, accessory {row.get('Acc Sale', 'unknown')}, MTD {row.get('MTD Tot', 'unknown')}"
            for idx, row in enumerate(rows, start=1)
        ]
        return AnswerResult(
            f"Previous-day Home rows: " + "; ".join(lines) + ".",
            ("home_dashboard",),
            report_range,
            len(rows),
            context={"last_stores": [row.get("Store Name / Company Name", "") for row in rows if row.get("Store Name / Company Name")], "last_metric": "previous day"},
        )

    summary = snapshot.period_summary[0] if snapshot.period_summary else {}
    if "conversion" in lowered:
        answer = f"Home period conversion is {summary.get('Conversion (CPD)', 'unknown')} with {summary.get('Qpay Count', 'unknown')} qpay count and {summary.get('Total Activation', 'unknown')} activations."
    elif "accessory" in lowered:
        answer = f"Home period accessory total is {summary.get('Accessory', 'unknown')} across {summary.get('Store Count', 'unknown')} stores; APD is {summary.get('Acc. Per Door (APD)', 'unknown')}."
    elif "activation" in lowered or "how are we doing" in lowered or "doing" in lowered:
        answer = (
            f"Home period summary: {summary.get('Total Activation', 'unknown')} activations, "
            f"{summary.get('Act. Per Door (PPD)', 'unknown')} PPD, {summary.get('Accessory', 'unknown')} accessory, "
            f"{summary.get('Qpay Count', 'unknown')} qpay, {summary.get('Conversion (CPD)', 'unknown')} conversion."
        )
    else:
        answer = (
            f"Home dashboard summary: {summary.get('Total Activation', 'unknown')} activations, "
            f"{summary.get('Accessory', 'unknown')} accessory, {summary.get('Conversion (CPD)', 'unknown')} conversion. "
            f"Today: {', '.join(f'{key}: {value}' for key, value in snapshot.today_snapshot.items())}."
        )

    return AnswerResult(
        answer,
        ("home_dashboard",),
        report_range,
        len(snapshot.period_summary),
        context={"last_metric": "home dashboard"},
    )
