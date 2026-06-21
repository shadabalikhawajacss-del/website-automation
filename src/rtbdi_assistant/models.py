from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

SourceType = Literal["dashboard", "grid", "export", "grid_or_export", "unknown"]


@dataclass(frozen=True)
class Column:
    name: str
    meaning: str
    data_type: str = "unknown"
    semantic_tags: tuple[str, ...] = ()
    source: str = "export"


@dataclass(frozen=True)
class FilterControl:
    name: str
    control_type: str
    required: bool = False
    notes: str = ""


@dataclass(frozen=True)
class Report:
    id: str
    name: str
    tab: str
    url_path: str | None
    source_type: SourceType
    filters: tuple[FilterControl, ...] = ()
    controls: tuple[str, ...] = ()
    columns: tuple[Column, ...] = ()
    aliases: tuple[str, ...] = ()
    join_keys: tuple[str, ...] = ()
    screenshot_folder: str | None = None
    export_sample: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class KnowledgeMap:
    site: str
    generated_from: tuple[str, ...]
    reports: tuple[Report, ...]

    def get(self, report_id: str) -> Report:
        for report in self.reports:
            if report.id == report_id:
                return report
        raise KeyError(f"Unknown report id: {report_id}")


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    label: str
    explicit: bool


@dataclass(frozen=True)
class MetricCandidate:
    report_id: str
    column: str
    reason: str


@dataclass(frozen=True)
class QueryPlan:
    question: str
    date_range: DateRange
    report_ids: tuple[str, ...]
    metrics: tuple[MetricCandidate, ...] = ()
    filters: dict[str, Any] = field(default_factory=dict)
    joins: tuple[str, ...] = ()
    needs_clarification: str | None = None
    notes: tuple[str, ...] = ()
