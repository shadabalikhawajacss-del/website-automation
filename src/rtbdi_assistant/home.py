from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.async_api import Page


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
