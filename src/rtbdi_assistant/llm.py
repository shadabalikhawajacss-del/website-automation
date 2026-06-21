from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import AssistantConfig
from .intent import ConversationMemory, LiveIntent, live_intent_from_llm_payload, select_live_reports
from .knowledge import load_knowledge
from .models import KnowledgeMap, QueryPlan
from .planner import plan_question, plan_to_dict

LIVE_REPORT_ROUTE_HINTS = {
    "home_dashboard": "Home dashboard: today snapshot, top stores now, company summary, dashboard/how are we doing questions.",
    "employee_conversion_ratio": "Employee conversion ratio and qpay count.",
    "employee_performance_report": "Employee/store basics, hours, accessory sales, activations, store rankings.",
    "employee_ranking_by_box_sales": "Top/bottom/ranking by activations, phones, accessory sales.",
    "employee_mrc_matrix_report": "Plan mix and device add-on mix for employees.",
    "kpi_report_by_employee": "Gross profit, KPI revenue, payment/MRC/feature revenue.",
    "finance_report": "Financed amount, approved finance amount, finance company, finance deals.",
    "trade_in_custom_report": "Trade-ins by carrier/make/model.",
    "bill_payment_listing": "Bill payment totals, bill payment profit/tax.",
    "phone_trend_by_market": "Phone trend, 7/14/30-day sales, slow movers.",
    "inventory_report": "Inventory/stock/on-hand, manufacturers, inventory value.",
    "po_listing_report": "PO/open purchase order amounts and vendors.",
    "inventory_transfer_listing": "Inventory transfer costs and transfer summaries.",
    "inventory_audit_log": "Inventory audit unmatched/missing counts.",
    "inventory_tangible_audit_log": "Tangible audit variance/scanned/system counts.",
}


def reconcile_live_intent(deterministic: LiveIntent, llm_intent: LiveIntent | None) -> LiveIntent:
    """Keep LLM routing inside safe deterministic guardrails.

    The deterministic layer catches concrete product/model/report words. If the
    LLM falls back to the broad Employee Performance report while deterministic
    routing found a more specific report, prefer the deterministic route.
    """

    if llm_intent is None:
        return deterministic
    if deterministic.confidence >= 0.95:
        return deterministic
    if llm_intent.needs_clarification:
        return llm_intent
    if not llm_intent.report_ids:
        return deterministic
    if (
        deterministic.report_ids != ("employee_performance_report",)
        and llm_intent.report_ids == ("employee_performance_report",)
    ):
        return deterministic
    return llm_intent


def compact_knowledge_summary(knowledge: KnowledgeMap, max_columns_per_report: int = 30) -> list[dict[str, Any]]:
    """Return the part of the report map that is useful in an LLM prompt."""

    summary: list[dict[str, Any]] = []
    for report in knowledge.reports:
        summary.append(
            {
                "id": report.id,
                "name": report.name,
                "tab": report.tab,
                "source_type": report.source_type,
                "aliases": list(report.aliases),
                "join_keys": list(report.join_keys),
                "columns": [
                    {
                        "name": column.name,
                        "meaning": column.meaning,
                        "data_type": column.data_type,
                        "semantic_tags": list(column.semantic_tags),
                    }
                    for column in report.columns[:max_columns_per_report]
                ],
                "notes": report.notes,
            }
        )
    return summary


def build_interpreter_messages(question: str, deterministic_plan: QueryPlan, knowledge: KnowledgeMap) -> list[dict[str, str]]:
    system = (
        "You translate plain-English RT BDI reporting questions into a safe execution plan. "
        "Use only the supplied report map and deterministic plan. Do not invent reports, "
        "columns, stores, employees, or numbers. If the question is ambiguous, ask for clarification. "
        "Dates must remain explicit; when no date is provided, keep month-to-date. "
        "Return JSON with keys: report_ids, metrics, filters, joins, needs_clarification, reasoning."
    )
    user = {
        "question": question,
        "deterministic_plan": plan_to_dict(deterministic_plan),
        "report_map": compact_knowledge_summary(knowledge),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]


class OpenAIInterpreter:
    """LLM adapter for interpreting questions before live report execution."""

    def __init__(self, config: AssistantConfig | None = None, knowledge: KnowledgeMap | None = None):
        self.config = config or AssistantConfig.from_env()
        self.knowledge = knowledge or load_knowledge()
        self.client = OpenAI(api_key=self.config.require_openai_key())

    def interpret(self, question: str) -> dict[str, Any]:
        deterministic_plan = plan_question(question, self.knowledge)
        messages = build_interpreter_messages(question, deterministic_plan, self.knowledge)
        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        llm_payload = json.loads(content)
        return {
            "question": question,
            "deterministic_plan": plan_to_dict(deterministic_plan),
            "llm_interpretation": llm_payload,
        }

    def route_live_intent(self, question: str, memory: ConversationMemory | None = None) -> LiveIntent:
        deterministic = select_live_reports(question, memory)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are routing an RT BDI chatbot question. Choose the live reports needed to answer. "
                    "Use only the supported report IDs provided. Return JSON only with keys: "
                    "canonical_question, report_ids, needs_clarification, reasoning. "
                    "If ambiguous, set needs_clarification and use an empty report_ids array. "
                    "Do not invent report IDs or numbers."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "memory": {
                            "last_employee": memory.last_employee if memory else None,
                            "second_employee": memory.second_employee if memory else None,
                            "last_stores": memory.last_stores if memory else [],
                            "last_metric": memory.last_metric if memory else None,
                        },
                        "deterministic_fallback": {
                            "canonical_question": deterministic.canonical_question,
                            "report_ids": list(deterministic.report_ids),
                        },
                        "supported_reports": LIVE_REPORT_ROUTE_HINTS,
                    }
                ),
            },
        ]
        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return reconcile_live_intent(deterministic, live_intent_from_llm_payload(question, payload, memory))


def select_live_intent(question: str, memory: ConversationMemory | None = None, config: AssistantConfig | None = None) -> LiveIntent:
    config = config or AssistantConfig.from_env()
    if not config.openai_api_key:
        return select_live_reports(question, memory)
    try:
        return OpenAIInterpreter(config=config).route_live_intent(question, memory)
    except Exception:
        return select_live_reports(question, memory)


def preview_interpreter_prompt(question: str, knowledge: KnowledgeMap | None = None) -> dict[str, Any]:
    km = knowledge or load_knowledge()
    deterministic_plan = plan_question(question, km)
    return {
        "question": question,
        "deterministic_plan": plan_to_dict(deterministic_plan),
        "messages": build_interpreter_messages(question, deterministic_plan, km),
    }
