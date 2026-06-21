from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import AssistantConfig
from .knowledge import load_knowledge
from .models import KnowledgeMap, QueryPlan
from .planner import plan_question, plan_to_dict


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


def preview_interpreter_prompt(question: str, knowledge: KnowledgeMap | None = None) -> dict[str, Any]:
    km = knowledge or load_knowledge()
    deterministic_plan = plan_question(question, km)
    return {
        "question": question,
        "deterministic_plan": plan_to_dict(deterministic_plan),
        "messages": build_interpreter_messages(question, deterministic_plan, km),
    }
