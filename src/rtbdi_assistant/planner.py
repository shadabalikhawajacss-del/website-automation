from __future__ import annotations

import re
from dataclasses import asdict

from .dates import resolve_date_range
from .knowledge import load_knowledge
from .models import KnowledgeMap, MetricCandidate, QueryPlan

AMBIGUOUS_PRONOUN = re.compile(r"\b(she|he|they|her|him|their|that person)\b", re.IGNORECASE)
AMBIGUOUS_REQUESTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("show me the ranking", "show ranking"), "Which metric should the ranking use?"),
    (("compare the two stores",), "Which two stores should be compared?"),
    (("best employee",), "Best employee by which metric: activations, accessories, conversion, gross profit, or another metric?"),
    (("how are we doing",), "Which summary should I run: sales, employee performance, inventory, finance, or profitability?"),
)

REPORT_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("conversion", "ratio", "qpay"), ("employee_conversion_ratio",)),
    (("full name", "user id", "first and last name", "hours", "worked", "staff"), ("employee_performance_report",)),
    (("finance", "financed", "application", "approved amount"), ("finance_report", "employee_ranking_by_finance")),
    (("bill", "payment"), ("bill_payment_listing",)),
    (("trade", "trade-in", "trade-ins", "rma", "carrier", "make and model"), ("trade_in_custom_report",)),
    (("profit loss", "p&l", "pnl"), ("profit_loss_report",)),
    (("inventory", "stock", "on hand", "phones in store", "apple", "samsung", "motorola", "serialized", "non-serialized", "tripsim", "triplesim"), ("inventory_report",)),
    (("transfer",), ("inventory_transfer_listing", "inventory_transfer_detail")),
    (("po", "purchase order", "open po", "open amount", "reconciled"), ("po_listing_report", "open_po_report")),
    (("audit", "variance", "scanned", "system", "unmatched"), ("inventory_audit_log", "inventory_tangible_audit_log")),
    (("serial", "imei"), ("serial_number_report", "serial_number_tracking")),
    (("mrc", "plan mix", "rate plan", "$60", "$50", "flex 60", "aal", "tablet", "hotspot", "watch", "insurance", "secure5", "secure10", "php", "phone protection", "smartride", "smart ride", "iot"), ("employee_mrc_matrix_report", "activation_mrc_by_employee")),
    (("gross profit", "gp", "feature revenue", "mrc revenue"), ("kpi_report_by_employee",)),
    (("a16", "revvl", "fastest-selling", "slow movers", "sold in the last", "sold in last", "30-day sales", "7-day"), ("phone_trend_by_market", "phone_trend_by_market_item_or_model")),
    (("accessor", "accessories"), ("employee_performance_report", "kpi_report_by_employee")),
    (("top", "rank", "seller", "boxes", "phones", "activation"), ("employee_ranking_by_box_sales", "box_report_by_employee")),
)

METRIC_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("conversion", "ratio"), "employee_conversion_ratio", "ratio"),
    (("qpay",), "employee_conversion_ratio", "totqty"),
    (("full name", "first and last name"), "employee_performance_report", "name"),
    (("user id",), "employee_performance_report", "username"),
    (("employee", "employees", "staff"), "employee_performance_report", "name"),
    (("hours", "worked"), "employee_performance_report", "hoursworked"),
    (("accessor", "accessories"), "employee_performance_report", "totaccessory"),
    (("accessory profit",), "employee_performance_report", "totaccessoryprofit"),
    (("accessory-per-hour", "aph"), "employee_performance_report", "aph"),
    (("accessory revenue",), "kpi_report_by_employee", "accessoryrev"),
    (("accessory revenue to cost", "revenue to cost"), "kpi_report_by_employee", "accessorycost"),
    (("gross profit", "gp"), "kpi_report_by_employee", "grossprofit"),
    (("feature revenue",), "kpi_report_by_employee", "feature_rev"),
    (("mrc revenue",), "kpi_report_by_employee", "mrc_rev"),
    (("payment revenue",), "kpi_report_by_employee", "paymentrev"),
    (("phones", "boxes", "activation"), "employee_ranking_by_box_sales", "totact"),
    (("plan mix", "mrc", "rate plan"), "employee_mrc_matrix_report", "totact"),
    (("$60", "60 plans", "plan60"), "employee_mrc_matrix_report", "plan60"),
    (("flex 60",), "employee_mrc_matrix_report", "flex60"),
    (("$50 aal", "50 aal"), "employee_mrc_matrix_report", "plan50aal"),
    (("$50", "50 plans"), "employee_mrc_matrix_report", "plan50"),
    (("tablet", "tablets"), "employee_mrc_matrix_report", "tablet20"),
    (("hotspot", "hotspots"), "employee_mrc_matrix_report", "hotspot"),
    (("watch", "watches"), "employee_mrc_matrix_report", "watch"),
    (("insurance", "secure5"), "employee_mrc_matrix_report", "secure5"),
    (("insurance", "secure10"), "employee_mrc_matrix_report", "secure10"),
    (("php", "phone protection"), "employee_mrc_matrix_report", "php"),
    (("smartride", "smart ride"), "employee_mrc_matrix_report", "smartride"),
    (("iot",), "employee_mrc_matrix_report", "iot"),
    (("inventory", "stock", "on hand"), "inventory_report", "qty"),
    (("inventory value", "stock value", "qty x cost"), "inventory_report", "cost"),
    (("apple", "samsung", "motorola", "manufacturer"), "inventory_report", "manufacturer"),
    (("black", "color"), "inventory_report", "color"),
    (("serialized", "non-serialized"), "inventory_report", "serialized"),
    (("tripsim", "triplesim"), "inventory_report", "item"),
    (("7 days", "7-day", "last 7"), "phone_trend_by_market", "sale7"),
    (("30 days", "30-day", "last 30", "fastest-selling", "slow movers"), "phone_trend_by_market", "sale30"),
    (("model", "a16", "revvl"), "phone_trend_by_market_item_or_model", "itmdesc"),
    (("on hand", "high stock"), "phone_trend_by_market", "onhand"),
    (("finance", "financed"), "finance_report", "Financed Amount"),
    (("approved amount",), "finance_report", "Approved Amount"),
    (("finance company",), "finance_report", "Finance Company"),
    (("trade-ins", "trade in", "trade-in"), "trade_in_custom_report", "TI Applied"),
    (("carrier",), "trade_in_custom_report", "Carrier"),
    (("make",), "trade_in_custom_report", "Make"),
    (("model",), "trade_in_custom_report", "Model"),
    (("payment",), "bill_payment_listing", "total"),
    (("open amount", "open po"), "po_listing_report", "openamount"),
    (("vendor",), "po_listing_report", "vendor"),
    (("reconciled",), "po_listing_report", "isreconciled"),
    (("variance",), "inventory_tangible_audit_log", "varianceqty"),
    (("scanned",), "inventory_tangible_audit_log", "scanqty"),
    (("system",), "inventory_tangible_audit_log", "sysqty"),
    (("unmatched",), "inventory_audit_log", "unmatchedcount"),
    (("transfer cost",), "inventory_transfer_listing", "cost"),
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
    clarification = None
    for terms, message in AMBIGUOUS_REQUESTS:
        if _contains_any(lowered, terms):
            clarification = message

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

    if "multiple" in lowered:
        clarification = "There may be multiple matching people or stores. Which exact one should I use?"
    elif AMBIGUOUS_PRONOUN.search(question) and not report_ids:
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
