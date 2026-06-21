from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .exports import infer_header, read_export
from .models import DateRange
from .numeric import parse_decimal
from .planner import plan_question


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    reports_used: tuple[str, ...]
    date_range: DateRange
    rows_used: int
    notes: tuple[str, ...] = ()


STOPWORDS = {
    "accessory",
    "activations",
    "at",
    "conversion",
    "did",
    "does",
    "employee",
    "for",
    "full",
    "how",
    "is",
    "many",
    "name",
    "ratio",
    "sales",
    "store",
    "the",
    "total",
    "user",
    "what",
    "which",
    "work",
}


def load_export_table(path: Path) -> pd.DataFrame:
    sheets = read_export(path)
    _, raw = next(iter(sheets.items()))
    header_index, columns = infer_header(raw)
    data = raw.iloc[header_index + 1 :].copy()
    data = data.iloc[:, : len(columns)]
    data.columns = list(columns)
    data = data.dropna(how="all")
    return data.reset_index(drop=True)


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def display_value(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def employee_name(row: pd.Series) -> str:
    first = str(row.get("name") or "").strip()
    last = str(row.get("lastname") or "").strip()
    full = " ".join(part for part in (first, last) if part)
    return full or "unknown"


def decimal_sum(values: pd.Series) -> Decimal:
    total = Decimal("0")
    for value in values:
        parsed = parse_decimal(value)
        if parsed is not None:
            total += parsed
    return total


def decimal_mean(values: pd.Series) -> Decimal | None:
    parsed = [value for value in (parse_decimal(item) for item in values) if value is not None]
    if not parsed:
        return None
    return sum(parsed, Decimal("0")) / Decimal(len(parsed))


def money(value: Decimal) -> str:
    return f"${value:,.2f}"


def number(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def percent(value: object) -> str:
    parsed = parse_decimal(value)
    if parsed is None:
        return display_value(value)
    return f"{parsed:,.2f}%"


def extract_store_text(question: str) -> str | None:
    match = re.search(r"\b(rockon\s+[a-z0-9 '&.-]+)", question, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(" ?.!")
    match = re.search(r"\bat\s+([a-z0-9][a-z0-9 '&.-]+)", question, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(" ?.!")
    return None


def filter_store(df: pd.DataFrame, question: str) -> tuple[pd.DataFrame, str | None]:
    store_text = extract_store_text(question)
    if not store_text or "company" not in df.columns:
        return df, None
    needle = normalize_text(store_text)
    filtered = df[df["company"].map(lambda value: needle in normalize_text(value))]
    return filtered, store_text


def _question_tokens(question: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9']+", question)
    return [token.casefold().strip("'") for token in tokens if token.casefold().strip("'") not in STOPWORDS and len(token) > 1]


def find_employee_rows(df: pd.DataFrame, question: str) -> pd.DataFrame:
    if not {"username", "name"}.issubset(df.columns):
        return df.iloc[0:0]

    user_match = re.search(r"\b[a-z]{2,}\d{3,}\b", question, flags=re.IGNORECASE)
    if user_match:
        needle = user_match.group(0).casefold()
        return df[df["username"].map(lambda value: normalize_text(value) == needle)]

    tokens = _question_tokens(question)
    if not tokens:
        return df.iloc[0:0]

    def score(row: pd.Series) -> int:
        haystack = f"{normalize_text(row.get('username'))} {normalize_text(row.get('name'))} {normalize_text(row.get('lastname'))}"
        return sum(1 for token in tokens if token in haystack)

    scores = df.apply(score, axis=1)
    max_score = int(scores.max()) if len(scores) else 0
    if max_score <= 0:
        return df.iloc[0:0]
    return df[scores == max_score]


def _employee_rows(df: pd.DataFrame, question: str) -> tuple[pd.DataFrame, str | None]:
    rows = find_employee_rows(df, question)
    if rows.empty:
        return rows, "I could not find a matching employee in the downloaded report."
    identity_columns = [column for column in ("username", "name", "lastname") if column in rows.columns]
    identities = rows[identity_columns].drop_duplicates()
    if len(identities) > 1:
        names = ", ".join(
            " / ".join(display_value(row.get(column)) for column in identities.columns)
            for _, row in identities.head(10).iterrows()
        )
        return rows.iloc[0:0], f"I found multiple matching employees: {names}. Please give the full name or user ID."
    return rows, None


def answer_from_exports(question: str, exports: dict[str, Path]) -> AnswerResult:
    plan = plan_question(question)
    lowered = question.casefold()

    if "employee_conversion_ratio" in exports and ("conversion" in lowered or "ratio" in lowered or "qpay" in lowered):
        return _answer_conversion(question, exports["employee_conversion_ratio"], plan.date_range)

    if "employee_performance_report" in exports:
        return _answer_performance(question, exports["employee_performance_report"], plan.date_range)

    raise ValueError("No supported export was supplied for this question yet")


def _answer_conversion(question: str, path: Path, date_range: DateRange) -> AnswerResult:
    df = load_export_table(path)
    filtered, store_text = filter_store(df, question)
    lowered = question.casefold()

    if "average" in lowered and store_text:
        avg = decimal_mean(filtered["ratio"])
        if avg is None:
            answer = f"I found no conversion-ratio rows for {store_text}."
        else:
            answer = f"Average conversion ratio at {store_text} is {avg:,.2f}%."
        return AnswerResult(answer, ("employee_conversion_ratio",), date_range, len(filtered))

    rows, problem = _employee_rows(filtered, question)
    if problem:
        return AnswerResult(problem, ("employee_conversion_ratio",), date_range, 0)

    employee = rows.iloc[0]
    name = employee_name(employee)
    username = display_value(employee.get("username"))
    parts = []
    if "qpay" in lowered:
        parts.append(f"qpay count is {number(decimal_sum(rows['totqty']))}")
    if "conversion" in lowered or "ratio" in lowered:
        activations = decimal_sum(rows["totact"])
        qpay = decimal_sum(rows["totqty"])
        ratio = (activations / qpay * Decimal("100")) if qpay else None
        if ratio is None:
            parts.append("conversion ratio could not be calculated because qpay count is zero")
        else:
            parts.append(f"conversion ratio is {ratio:,.2f}%")
    if not parts:
        parts.append(f"conversion ratio is {percent(employee.get('ratio'))}")
    return AnswerResult(f"{name} ({username}) " + " and ".join(parts) + ".", ("employee_conversion_ratio",), date_range, len(rows))


def _answer_performance(question: str, path: Path, date_range: DateRange) -> AnswerResult:
    df = load_export_table(path)
    filtered, store_text = filter_store(df, question)
    lowered = question.casefold()

    if ("how many employees" in lowered or "employees at" in lowered or "employees work" in lowered) and store_text:
        count = filtered["username"].nunique() if "username" in filtered.columns else len(filtered)
        return AnswerResult(f"{store_text} has {count:,} employees in Employee Performance Report.", ("employee_performance_report",), date_range, len(filtered))

    if store_text and ("total accessory" in lowered or "accessory sales" in lowered):
        column = "totaccessoryprofit" if "profit" in lowered else "totaccessory"
        total = decimal_sum(filtered[column]) if column in filtered.columns else Decimal("0")
        label = "accessory profit" if column == "totaccessoryprofit" else "accessory sales"
        return AnswerResult(f"Total {label} at {store_text} is {money(total)}.", ("employee_performance_report",), date_range, len(filtered))

    if store_text and ("total boxes" in lowered or "total activations" in lowered or "phones" in lowered):
        total = decimal_sum(filtered["totact"]) if "totact" in filtered.columns else Decimal("0")
        return AnswerResult(f"Total activations at {store_text} are {number(total)}.", ("employee_performance_report",), date_range, len(filtered))

    rows, problem = _employee_rows(filtered, question)
    if problem:
        return AnswerResult(problem, ("employee_performance_report",), date_range, 0)

    employee = rows.iloc[0]
    name = employee_name(employee)
    username = display_value(employee.get("username"))
    stores = sorted({display_value(value) for value in rows.get("company", [])})
    store = ", ".join(stores) if stores else "unknown"

    if "which store" in lowered or lowered.endswith("store?"):
        answer = f"{name} ({username}) works at {store}."
    elif "full name" in lowered or "first and last name" in lowered or "user id" in lowered:
        answer = f"Full name: {name}. User ID: {username}. Store: {store}."
    elif "hours" in lowered or "worked" in lowered:
        answer = f"{name} ({username}) worked {number(decimal_sum(rows['hoursworked']))} hours."
    elif "accessory" in lowered:
        value = decimal_sum(rows["totaccessory"])
        answer = f"{name} ({username}) accessory sales are {money(value)} at {store}."
    elif "activation" in lowered or "boxes" in lowered or "phones" in lowered:
        value = decimal_sum(rows["totact"])
        answer = f"{name} ({username}) total activations are {number(value)}."
    else:
        answer = f"{name} ({username}) works at {store}."

    return AnswerResult(answer, ("employee_performance_report",), date_range, len(rows))
