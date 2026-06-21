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

    if {"employee_ranking_by_box_sales", "employee_mrc_matrix_report", "kpi_report_by_employee", "inventory_report"}.issubset(exports) and (
        "plan mix" in lowered or ("inventory" in lowered and "gross profit" in lowered)
    ):
        return _answer_top_seller_multireport(question, exports, plan.date_range)

    if {"employee_ranking_by_box_sales", "kpi_report_by_employee"}.issubset(exports) and "accessor" in lowered and (
        "gross profit" in lowered or "store" in lowered
    ):
        return _answer_top_accessory_with_kpi(question, exports, plan.date_range)

    if "employee_ranking_by_box_sales" in exports and ("top" in lowered or "rank" in lowered or "most" in lowered or "bottom" in lowered):
        return _answer_employee_ranking(question, exports["employee_ranking_by_box_sales"], plan.date_range)

    if "kpi_report_by_employee" in exports and ("gross profit" in lowered or "payment revenue" in lowered or "mrc revenue" in lowered):
        return _answer_kpi_ranking(question, exports["kpi_report_by_employee"], plan.date_range)

    if "employee_conversion_ratio" in exports and ("conversion" in lowered or "ratio" in lowered or "qpay" in lowered):
        return _answer_conversion(question, exports["employee_conversion_ratio"], plan.date_range)

    if "employee_performance_report" in exports:
        return _answer_performance(question, exports["employee_performance_report"], plan.date_range)

    raise ValueError("No supported export was supplied for this question yet")


def _top_n(question: str, default: int = 5) -> int:
    match = re.search(r"\b(?:top|bottom|rank)\s+(\d+)", question, flags=re.IGNORECASE)
    return int(match.group(1)) if match else default


def _rank_metric(question: str) -> tuple[str, str, bool]:
    lowered = question.casefold()
    if "accessory profit" in lowered:
        return "totaccessoryprofit", "accessory profit", True
    if "accessor" in lowered:
        return "totaccessory", "accessory sales", True
    if "hour" in lowered and ("box" in lowered or "activation" in lowered):
        return "hoursworked", "hours worked", False
    if "finance" in lowered:
        return "financecount", "finance count", True
    return "totact", "total activations", True


def _employee_group(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows = []
    for (username, name), group in df.groupby(["username", "name"], dropna=False):
        rows.append(
            {
                "username": username,
                "name": name,
                metric: decimal_sum(group[metric]) if metric in group.columns else Decimal("0"),
                "rows": len(group),
            }
        )
    return pd.DataFrame(rows)


def _answer_employee_ranking(question: str, path: Path, date_range: DateRange) -> AnswerResult:
    df = load_export_table(path)
    metric, label, descending = _rank_metric(question)
    if metric not in df.columns:
        return AnswerResult(f"The ranking export does not include {label}.", ("employee_ranking_by_box_sales",), date_range, len(df))
    ranked = _employee_group(df, metric).sort_values(metric, ascending=not descending).head(_top_n(question))
    lines = []
    for idx, row in enumerate(ranked.itertuples(index=False), start=1):
        value = getattr(row, metric)
        rendered = money(value) if "accessory" in label else number(value)
        lines.append(f"{idx}. {display_value(row.name)} ({display_value(row.username)}) - {rendered}")
    return AnswerResult(
        f"Top {len(lines)} employees by {label}: " + "; ".join(lines) + ".",
        ("employee_ranking_by_box_sales",),
        date_range,
        len(df),
    )


def _answer_kpi_ranking(question: str, path: Path, date_range: DateRange) -> AnswerResult:
    df = load_export_table(path)
    lowered = question.casefold()
    if "payment revenue" in lowered:
        metric, label = "paymentrev", "payment revenue"
    elif "mrc revenue" in lowered:
        metric, label = "mrc_rev", "MRC revenue"
    else:
        metric, label = "grossprofit", "gross profit"
    rows = []
    for (username, name), group in df.groupby(["username", "name"], dropna=False):
        rows.append({"username": username, "name": name, metric: decimal_sum(group[metric])})
    ranked = pd.DataFrame(rows).sort_values(metric, ascending=False).head(_top_n(question, default=3))
    lines = [
        f"{idx}. {display_value(row.name)} ({display_value(row.username)}) - {money(getattr(row, metric))}"
        for idx, row in enumerate(ranked.itertuples(index=False), start=1)
    ]
    return AnswerResult(f"Top {len(lines)} employees by {label}: " + "; ".join(lines) + ".", ("kpi_report_by_employee",), date_range, len(df))


PLAN_COLUMNS = (
    "plan25",
    "plan30",
    "plan40",
    "plan50",
    "flex70",
    "flex60",
    "flex50",
    "plan50aal",
    "plan60",
    "plan60aal",
    "upgrade",
    "sor",
    "php",
    "secure5",
    "secure10",
    "hotspot",
    "watch",
    "smartride",
    "tablet15",
    "tablet20",
    "tablet30",
    "iot",
    "freeline",
)


def _sum_for_user(df: pd.DataFrame, username: object, column: str) -> Decimal:
    if column not in df.columns or "username" not in df.columns:
        return Decimal("0")
    rows = df[df["username"].map(normalize_text) == normalize_text(username)]
    return decimal_sum(rows[column])


def _top_users_by_activations(ranking: pd.DataFrame, count: int = 2) -> pd.DataFrame:
    grouped = _employee_group(ranking, "totact")
    return grouped.sort_values("totact", ascending=False).head(count)


def _answer_top_seller_multireport(question: str, exports: dict[str, Path], date_range: DateRange) -> AnswerResult:
    ranking = load_export_table(exports["employee_ranking_by_box_sales"])
    mrc = load_export_table(exports["employee_mrc_matrix_report"])
    kpi = load_export_table(exports["kpi_report_by_employee"])
    inventory = load_export_table(exports["inventory_report"])

    top_two = _top_users_by_activations(ranking, 2)
    if len(top_two) < 2:
        return AnswerResult("I could not find the top two employees by activations.", tuple(exports), date_range, len(ranking))

    top = top_two.iloc[0]
    second = top_two.iloc[1]
    top_username = top["username"]
    second_username = second["username"]

    plan_parts = []
    top_mrc = mrc[mrc["username"].map(normalize_text) == normalize_text(top_username)] if "username" in mrc.columns else mrc.iloc[0:0]
    for column in PLAN_COLUMNS:
        if column in top_mrc.columns:
            value = decimal_sum(top_mrc[column])
            if value:
                plan_parts.append(f"{column} {number(value)}")
    plan_summary = ", ".join(plan_parts[:8]) if plan_parts else "no non-zero plan/device columns found"

    top_kpi = kpi[kpi["username"].map(normalize_text) == normalize_text(top_username)] if "username" in kpi.columns else kpi.iloc[0:0]
    second_kpi = kpi[kpi["username"].map(normalize_text) == normalize_text(second_username)] if "username" in kpi.columns else kpi.iloc[0:0]
    top_gp = decimal_sum(top_kpi["grossprofit"]) if "grossprofit" in top_kpi.columns else Decimal("0")
    second_gp = decimal_sum(second_kpi["grossprofit"]) if "grossprofit" in second_kpi.columns else Decimal("0")
    gp_delta = top_gp - second_gp

    stores = sorted({display_value(value) for value in top_kpi.get("company", []) if display_value(value) != "unknown"})
    inv_rows = inventory[inventory["company"].map(lambda value: normalize_text(value) in {normalize_text(store) for store in stores})] if stores and "company" in inventory.columns else inventory.iloc[0:0]
    inv_qty = decimal_sum(inv_rows["qty"]) if "qty" in inv_rows.columns else Decimal("0")
    inv_value = Decimal("0")
    if {"qty", "cost"}.issubset(inv_rows.columns):
        for _, row in inv_rows.iterrows():
            qty = parse_decimal(row.get("qty")) or Decimal("0")
            cost = parse_decimal(row.get("cost")) or Decimal("0")
            inv_value += qty * cost

    answer = (
        f"Top employee by activations is {display_value(top['name'])} ({display_value(top_username)}) with {number(top['totact'])} activations. "
        f"#2 is {display_value(second['name'])} ({display_value(second_username)}) with {number(second['totact'])}. "
        f"Plan/device mix for #1: {plan_summary}. "
        f"#1 store(s): {', '.join(stores) if stores else 'not found in KPI report'}. "
        f"Those store(s) have {number(inv_qty)} inventory units on hand with estimated cost value {money(inv_value)}. "
        f"Gross profit: #1 {money(top_gp)} vs #2 {money(second_gp)} ({money(gp_delta)} difference)."
    )
    return AnswerResult(
        answer,
        ("employee_ranking_by_box_sales", "employee_mrc_matrix_report", "kpi_report_by_employee", "inventory_report"),
        date_range,
        len(ranking) + len(mrc) + len(kpi) + len(inventory),
    )


def _answer_top_accessory_with_kpi(question: str, exports: dict[str, Path], date_range: DateRange) -> AnswerResult:
    ranking = load_export_table(exports["employee_ranking_by_box_sales"])
    kpi = load_export_table(exports["kpi_report_by_employee"])
    ranked = _employee_group(ranking, "totaccessory").sort_values("totaccessory", ascending=False)
    if ranked.empty:
        return AnswerResult("I could not find accessory sales in the ranking report.", tuple(exports), date_range, len(ranking))
    top = ranked.iloc[0]
    top_username = top["username"]
    top_kpi = kpi[kpi["username"].map(normalize_text) == normalize_text(top_username)] if "username" in kpi.columns else kpi.iloc[0:0]
    stores = sorted({display_value(value) for value in top_kpi.get("company", []) if display_value(value) != "unknown"})
    gross_profit = decimal_sum(top_kpi["grossprofit"]) if "grossprofit" in top_kpi.columns else Decimal("0")
    answer = (
        f"Top accessory seller is {display_value(top['name'])} ({display_value(top_username)}) with {money(top['totaccessory'])} in accessory sales. "
        f"Their gross profit is {money(gross_profit)} and their store(s) are {', '.join(stores) if stores else 'not found in KPI report'}."
    )
    return AnswerResult(answer, ("employee_ranking_by_box_sales", "kpi_report_by_employee"), date_range, len(ranking) + len(kpi))


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

    if "store" in lowered and ("top" in lowered or "rank" in lowered or "most" in lowered or "worst" in lowered):
        return _answer_store_ranking(question, df, date_range)

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


def _answer_store_ranking(question: str, df: pd.DataFrame, date_range: DateRange) -> AnswerResult:
    lowered = question.casefold()
    if "accessory profit" in lowered:
        column, label, descending = "totaccessoryprofit", "accessory profit", True
    elif "accessor" in lowered:
        column, label, descending = "totaccessory", "accessory sales", True
    elif "worst" in lowered and "conversion" in lowered:
        column, label, descending = "boxperhour", "box per hour", False
    else:
        column, label, descending = "totact", "total activations", True
    if "company" not in df.columns or column not in df.columns:
        return AnswerResult(f"Employee Performance Report does not include the columns needed to rank stores by {label}.", ("employee_performance_report",), date_range, len(df))
    rows = []
    for company, group in df.groupby("company", dropna=False):
        rows.append({"company": company, column: decimal_sum(group[column])})
    ranked = pd.DataFrame(rows).sort_values(column, ascending=not descending).head(_top_n(question, default=5))
    lines = []
    for idx, row in enumerate(ranked.itertuples(index=False), start=1):
        value = getattr(row, column)
        rendered = money(value) if "accessory" in label else number(value)
        lines.append(f"{idx}. {display_value(row.company)} - {rendered}")
    return AnswerResult(f"Top {len(lines)} stores by {label}: " + "; ".join(lines) + ".", ("employee_performance_report",), date_range, len(df))
