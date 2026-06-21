from __future__ import annotations

import re
from dataclasses import asdict

from .dates import resolve_date_range
from .knowledge import load_knowledge
from .models import KnowledgeMap, MetricCandidate, QueryPlan

AMBIGUOUS_PRONOUN = re.compile(r"\b(she|he|they|her|him|their|that person)\b", re.IGNORECASE)

REPORT_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("conversion", "ratio"), ("employee_conversion_ratio",)),
    (("finance", "financed", "application"), ("finance_report", "employee_ranking_by_finance")),
    (("bill", "payment"), ("bill_payment_listing",)),
    (("trade", "rma"), ("trade_in_custom_report",)),
    (("profit loss", "p&l", "pnl"), ("profit_loss_report",)),
    (("inventory", "stock", "on hand", "phones in store"), ("inventory_report",)),
    (("transfer",), ("inventory_transfer_listing", "inventory_transfer_detail")),
    (("po", "purchase order", "open po"), ("po_listing_report", "open_po_report")),
    (("serial", "imei"), ("serial_number_report", "serial_number_tracking")),
    (("mrc", "plan mix", "rate plan"), ("employee_mrc_matrix_report", "activation_mrc_by_employee")),
    (("gross profit", "gp"), ("kpi_report_by_employee",)),
    (("accessor", "accessories"), ("employee_performance_report", "kpi_report_by_employee")),
    (("top", "rank", "seller", "boxes", "phones", "activation"), ("employee_ranking_by_box_sales", "box_report_by_employee")),
)

METRIC_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("conversion", "ratio"), "employee_conversion_ratio", "ratio"),
    (("accessor", "accessories"), "employee_performance_report", "totaccessory"),
    (("gross profit", "gp"), "kpi_report_by_employee", "grossprofit"),
    (("phones", "boxes", "activation"), "employee_ranking_by_box_sales", "totact"),
    (("plan mix", "mrc", "rate plan"), "employee_mrc_matrix_report", "totact"),
    (("inventory", "stock", "on hand"), "inventory_report", "qty"),
    (("finance", "financed"), "finance_report", "Financed Amount"),
    (("payment",), "bill_payment_listing", "total"),
)

JOIN_HINTS = {
    "employee": ("username", "name", "fk_ezposusers"),
    "store": ("custno", "company", "StoreID", "Store Name", "fk_store"),
    "item": ("item", "Item Number", "serial"),
}

STORE_FILTER_STOPWORDS = {
    "accessories",
    "activation",
    "activations",
    "finance",
    "gross profit",
    "inventory",
    "plan mix",
    "sales",
}


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _append_unique(target: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def plan_question(question: str, knowledge: KnowledgeMap | None = None) -> QueryPlan:
    km = knowledge or load_knowledge()
    lowered = question.casefold()
    date_range = resolve_date_range(question)

    report_ids: list[str] = []
    for terms, ids in REPORT_RULES:
        if _contains_any(lowered, terms):
            _append_unique(report_ids, ids)

    if not report_ids and _contains_any(lowered, ("store", "sales", "employee", "team")):
        report_ids.append("employee_performance_report")

    if _contains_any(lowered, ("top seller", "#1", "number 1", "rank")) and _contains_any(lowered, ("inventory", "gross profit", "plan mix", "#2", "number 2")):
        _append_unique(
            report_ids,
            (
                "employee_ranking_by_box_sales",
                "employee_mrc_matrix_report",
                "inventory_report",
                "kpi_report_by_employee",
            ),
        )

    known_ids = {report.id for report in km.reports}
    report_ids = [report_id for report_id in report_ids if report_id in known_ids]

    metrics: list[MetricCandidate] = []
    for terms, report_id, column in METRIC_RULES:
        if report_id in report_ids and _contains_any(lowered, terms):
            metrics.append(MetricCandidate(report_id, column, f"matched language: {', '.join(terms)}"))

    filters: dict[str, str] = {}
    store_match = re.search(r"\b(?:store named|store called|at|for)\s+([a-z0-9][a-z0-9 '&.-]{2,})", lowered)
    if store_match:
        store_text = store_match.group(1).strip(" ?.!")
        if store_text not in STORE_FILTER_STOPWORDS:
            filters["store_text"] = store_text
    team_match = re.search(r"\b([a-z][a-z0-9']+)\s+(?:team|group)\b", lowered)
    if team_match:
        filters["manager_team"] = team_match.group(1).strip("'")

    joins = []
    if len(report_ids) > 1:
        if _contains_any(lowered, ("employee", "seller", "their", "#1", "#2")):
            joins.extend(JOIN_HINTS["employee"])
        if _contains_any(lowered, ("store", "team", "inventory")):
            joins.extend(JOIN_HINTS["store"])
        if _contains_any(lowered, ("item", "serial", "inventory")):
            joins.extend(JOIN_HINTS["item"])

    clarification = None
    if AMBIGUOUS_PRONOUN.search(question) and not report_ids:
        clarification = "Who or which store should the pronoun refer to?"
    elif not report_ids:
        clarification = "I need to know which business area this question is about: sales, employee, inventory, finance, bill payment, or trade-in."

    notes = []
    if not date_range.explicit:
        notes.append("No date was mentioned, so the plan uses month-to-date to avoid the site's empty today-only default.")

    return QueryPlan(
        question=question,
        date_range=date_range,
        report_ids=tuple(report_ids),
        metrics=tuple(metrics),
        filters=filters,
        joins=tuple(dict.fromkeys(joins)),
        needs_clarification=clarification,
        notes=tuple(notes),
    )


def plan_to_dict(plan: QueryPlan) -> dict[str, object]:
    payload = asdict(plan)
    payload["date_range"]["start"] = plan.date_range.start.isoformat()
    payload["date_range"]["end"] = plan.date_range.end.isoformat()
    return payload
