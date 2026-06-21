from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LiveIntent:
    original_question: str
    canonical_question: str
    report_ids: tuple[str, ...]
    memory_used: bool = False
    reasoning: str | None = None
    needs_clarification: str | None = None
    confidence: float = 0.0


@dataclass
class ConversationMemory:
    last_employee: dict[str, str] | None = None
    second_employee: dict[str, str] | None = None
    last_stores: list[str] = field(default_factory=list)
    last_metric: str | None = None

    @classmethod
    def load(cls, path: Path | None) -> "ConversationMemory":
        if not path or not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            last_employee=payload.get("last_employee"),
            second_employee=payload.get("second_employee"),
            last_stores=list(payload.get("last_stores") or []),
            last_metric=payload.get("last_metric"),
        )

    def update(self, context: dict[str, Any] | None) -> None:
        if not context:
            return
        if context.get("last_employee"):
            self.last_employee = dict(context["last_employee"])
        if context.get("second_employee"):
            self.second_employee = dict(context["second_employee"])
        if context.get("last_stores"):
            self.last_stores = [str(store) for store in context["last_stores"]]
        if context.get("last_metric"):
            self.last_metric = str(context["last_metric"])

    def save(self, path: Path | None) -> None:
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "last_employee": self.last_employee,
                    "second_employee": self.second_employee,
                    "last_stores": self.last_stores,
                    "last_metric": self.last_metric,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bhandsets?\b", "phones"),
    (r"\bboxes\b", "activations"),
    (r"\bacts?\b", "activations"),
    (r"\bnew lines?\b", "activations"),
    (r"\bphone sales\b", "activations"),
    (r"\bacc\b", "accessory"),
    (r"\baccessories\b", "accessory sales"),
    (r"\battach\b", "accessory sales"),
    (r"\bmade us\b", "gross profit"),
    (r"\bmake us\b", "gross profit"),
    (r"(?<!gross )\bprofit\b", "gross profit"),
    (r"\bgp\b", "gross profit"),
    (r"\bnumber one\b", "top 1"),
    (r"\bno\.?\s*1\b", "top 1"),
    (r"\b#1\b", "top 1"),
    (r"\bsecond place\b", "#2"),
    (r"\b#2\b", "#2"),
    (r"\brate plan\b", "plan mix"),
    (r"\bplans?\b", "plan mix"),
    (r"\bstocks?\b", "inventory"),
    (r"\bon hand\b", "inventory"),
    (r"\bimei\b", "serial"),
)


def canonicalize_question(question: str, memory: ConversationMemory | None = None) -> tuple[str, bool]:
    canonical = question.strip()
    memory_used = False
    for pattern, replacement in PHRASE_REPLACEMENTS:
        canonical = re.sub(pattern, replacement, canonical, flags=re.IGNORECASE)

    memory = memory or ConversationMemory()
    if memory.last_employee and re.search(r"\b(they|their|them|he|she|him|her|that person|that employee)\b", canonical, flags=re.IGNORECASE):
        username = memory.last_employee.get("username")
        name = memory.last_employee.get("name")
        if username:
            canonical = re.sub(r"\b(they|their|them|he|she|him|her|that person|that employee)\b", f"{name or ''} {username}", canonical, flags=re.IGNORECASE)
            memory_used = True

    if memory.last_stores and re.search(r"\b(that store|their store|there)\b", canonical, flags=re.IGNORECASE):
        canonical = re.sub(r"\b(that store|their store|there)\b", memory.last_stores[0], canonical, flags=re.IGNORECASE)
        memory_used = True

    return canonical, memory_used


PRODUCT_WORDS = {
    "iphone",
    "ipad",
    "samsung",
    "galaxy",
    "a16",
    "a17",
    "revvl",
    "tripsim",
    "sim",
    "motorola",
    "moto",
    "nimbus",
    "case",
    "charger",
    "tablet",
    "watch",
}

STOCK_WORDS = {"inventory", "stock", "stocks", "on hand", "available", "left", "in stock", "how many"}
TREND_WORDS = {
    "sold",
    "sales",
    "sale7",
    "sale14",
    "sale30",
    "selling",
    "trend",
    "last 7",
    "last 14",
    "last 30",
    "30 day",
    "30-day",
    "7 day",
    "7-day",
    "fast",
    "slow",
}


def _has_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def skill_route(question: str, memory: ConversationMemory | None = None) -> LiveIntent | None:
    canonical, memory_used = canonicalize_question(question, memory)
    lowered = canonical.casefold()

    has_product = _has_any(lowered, PRODUCT_WORDS) or bool(re.search(r"\b[a-z]+\s*\d{1,3}\b", lowered))
    has_stock = _has_any(lowered, STOCK_WORDS)
    has_trend = _has_any(lowered, TREND_WORDS)

    if has_product and has_stock and has_trend:
        return LiveIntent(question, canonical, ("inventory_report", "phone_trend_by_market"), memory_used, reasoning="skill: product stock plus sales trend", confidence=0.98)
    if has_product and has_stock:
        return LiveIntent(question, canonical, ("inventory_report",), memory_used, reasoning="skill: product/model stock question maps to Inventory Report columns item/itmdesc/qty/cost", confidence=0.99)
    if has_product and has_trend:
        return LiveIntent(question, canonical, ("phone_trend_by_market",), memory_used, reasoning="skill: product/model sales trend question maps to Phone Trend sale7/sale14/sale30", confidence=0.98)

    if (
        "home" in lowered
        or "dashboard" in lowered
        or "how are we doing" in lowered
        or "today snapshot" in lowered
        or ("top" in lowered and "store" in lowered and ("right now" in lowered or "dashboard" in lowered))
        or ("company" in lowered and ("conversion" in lowered or "summary" in lowered))
    ):
        report_ids = ("home_dashboard",)
    elif "plan mix" in lowered and "inventory" in lowered and ("gross profit" in lowered or "#2" in lowered):
        report_ids = ("employee_ranking_by_box_sales", "employee_mrc_matrix_report", "kpi_report_by_employee", "inventory_report")
    elif "finance" in lowered and "gross profit" in lowered:
        report_ids = ("finance_report", "kpi_report_by_employee")
    elif "accessory" in lowered and ("gross profit" in lowered or "store" in lowered) and ("top" in lowered or "seller" in lowered or "most" in lowered):
        report_ids = ("employee_ranking_by_box_sales", "kpi_report_by_employee")
    elif "bill payment" in lowered or "bill pay" in lowered or "payment listing" in lowered:
        report_ids = ("bill_payment_listing",)
    elif "trade" in lowered or "carrier" in lowered or "make and model" in lowered:
        report_ids = ("trade_in_custom_report",)
    elif "finance" in lowered or "financed" in lowered or "approved amount" in lowered:
        report_ids = ("finance_report",)
    elif "slow mover" in lowered or "sold in the last" in lowered or "fastest-selling" in lowered or "30-day" in lowered or "7-day" in lowered or "a16" in lowered or "revvl" in lowered:
        report_ids = ("phone_trend_by_market",)
    elif "purchase order" in lowered or "open po" in lowered or ("po" in lowered and "top" not in lowered):
        report_ids = ("po_listing_report",)
    elif "transfer" in lowered:
        report_ids = ("inventory_transfer_listing",)
    elif "audit" in lowered or "variance" in lowered or "unmatched" in lowered:
        report_ids = ("inventory_tangible_audit_log",) if "tangible" in lowered or "variance" in lowered else ("inventory_audit_log",)
    elif (
        "inventory" in lowered
        or "apple" in lowered
        or "samsung" in lowered
        or "motorola" in lowered
        or "iphone" in lowered
        or "revvl" in lowered
        or "tripsim" in lowered
        or "serialized" in lowered
    ):
        report_ids = ("inventory_report",)
    elif ("top" in lowered or "rank" in lowered or "most" in lowered or "bottom" in lowered) and "gross profit" in lowered:
        report_ids = ("kpi_report_by_employee",)
    elif "store" in lowered and ("top" in lowered or "rank" in lowered or "most" in lowered or "worst" in lowered):
        report_ids = ("employee_performance_report",)
    elif ("top" in lowered or "rank" in lowered or "most" in lowered or "bottom" in lowered) and ("accessory" in lowered or "activation" in lowered or "phones" in lowered):
        report_ids = ("employee_ranking_by_box_sales",)
    elif "conversion" in lowered or "ratio" in lowered or "qpay" in lowered:
        report_ids = ("employee_conversion_ratio",)
    else:
        report_ids = ("employee_performance_report",)

    confidence = 0.55 if report_ids == ("employee_performance_report",) else 0.85
    return LiveIntent(question, canonical, report_ids, memory_used, reasoning="skill: deterministic report capability match", confidence=confidence)


def select_live_reports(question: str, memory: ConversationMemory | None = None) -> LiveIntent:
    return skill_route(question, memory) or LiveIntent(question, question, ("employee_performance_report",), reasoning="fallback", confidence=0.1)


SUPPORTED_LIVE_REPORTS = {
    "home_dashboard",
    "employee_conversion_ratio",
    "employee_performance_report",
    "employee_ranking_by_box_sales",
    "employee_mrc_matrix_report",
    "kpi_report_by_employee",
    "finance_report",
    "trade_in_custom_report",
    "bill_payment_listing",
    "phone_trend_by_market",
    "inventory_report",
    "po_listing_report",
    "inventory_transfer_listing",
    "inventory_audit_log",
    "inventory_tangible_audit_log",
}


def live_intent_from_llm_payload(question: str, payload: dict[str, Any], memory: ConversationMemory | None = None) -> LiveIntent | None:
    report_ids = tuple(report_id for report_id in payload.get("report_ids", []) if report_id in SUPPORTED_LIVE_REPORTS)
    if not report_ids and not payload.get("needs_clarification"):
        return None
    canonical, memory_used = canonicalize_question(str(payload.get("canonical_question") or question), memory)
    return LiveIntent(
        original_question=question,
        canonical_question=canonical,
        report_ids=report_ids,
        memory_used=memory_used,
        reasoning=payload.get("reasoning"),
        needs_clarification=payload.get("needs_clarification"),
    )
