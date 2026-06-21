from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Column, FilterControl, KnowledgeMap, Report

DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "report_map.json"


def _column(data: dict[str, Any]) -> Column:
    return Column(
        name=data["name"],
        meaning=data.get("meaning", ""),
        data_type=data.get("data_type", "unknown"),
        semantic_tags=tuple(data.get("semantic_tags", ())),
        source=data.get("source", "export"),
    )


def _filter(data: dict[str, Any]) -> FilterControl:
    return FilterControl(
        name=data["name"],
        control_type=data.get("control_type", "unknown"),
        required=bool(data.get("required", False)),
        notes=data.get("notes", ""),
    )


def _report(data: dict[str, Any]) -> Report:
    return Report(
        id=data["id"],
        name=data["name"],
        tab=data["tab"],
        url_path=data.get("url_path"),
        source_type=data.get("source_type", "unknown"),
        filters=tuple(_filter(item) for item in data.get("filters", ())),
        controls=tuple(data.get("controls", ())),
        columns=tuple(_column(item) for item in data.get("columns", ())),
        aliases=tuple(data.get("aliases", ())),
        join_keys=tuple(data.get("join_keys", ())),
        screenshot_folder=data.get("screenshot_folder"),
        export_sample=data.get("export_sample"),
        notes=data.get("notes", ""),
    )


@lru_cache(maxsize=4)
def load_knowledge(path: str | Path | None = None) -> KnowledgeMap:
    source = Path(path) if path else DEFAULT_KNOWLEDGE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    return KnowledgeMap(
        site=payload["site"],
        generated_from=tuple(payload.get("generated_from", ())),
        reports=tuple(_report(item) for item in payload.get("reports", ())),
    )


def find_reports(term: str, knowledge: KnowledgeMap | None = None) -> list[Report]:
    needle = term.casefold()
    km = knowledge or load_knowledge()
    matches: list[Report] = []
    for report in km.reports:
        haystack = " ".join((report.name, report.id, *report.aliases)).casefold()
        if needle in haystack:
            matches.append(report)
    return matches
