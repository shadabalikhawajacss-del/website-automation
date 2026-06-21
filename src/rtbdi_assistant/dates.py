from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

from .models import DateRange

MONTHS = {name.casefold(): index for index, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.casefold(): index for index, name in enumerate(calendar.month_abbr) if name})


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def default_month_to_date(today: date | None = None) -> DateRange:
    today = today or date.today()
    return DateRange(date(today.year, today.month, 1), today, "month-to-date", explicit=False)


def resolve_date_range(text: str, today: date | None = None) -> DateRange:
    """Resolve user date language into an inclusive report range.

    If no date is mentioned, RT BDI should use month-to-date instead of the
    site's default single-day current date because today's report is often empty.
    """

    today = today or date.today()
    value = text.casefold()

    if re.search(r"\b(month[- ]?to[- ]?date|mtd|this month)\b", value):
        return DateRange(date(today.year, today.month, 1), today, "month-to-date", explicit=True)

    if re.search(r"\b(year[- ]?to[- ]?date|ytd|this year)\b", value):
        return DateRange(date(today.year, 1, 1), today, "year-to-date", explicit=True)

    if re.search(r"\b(yesterday)\b", value):
        day = today - timedelta(days=1)
        return DateRange(day, day, "yesterday", explicit=True)

    match = re.search(r"\b(last|past|previous)\s+(\d+)\s+days?\b", value)
    if match:
        days = int(match.group(2))
        start = today - timedelta(days=days - 1)
        return DateRange(start, today, f"last {days} days", explicit=True)

    match = re.search(r"\b(last|past|previous)\s+(\d+)\s+months?\b", value)
    if match:
        months = int(match.group(2))
        start_month = today.replace(day=1) - relativedelta(months=months)
        end = today.replace(day=1) - timedelta(days=1)
        return DateRange(start_month, end, f"previous {months} full months", explicit=True)

    if re.search(r"\b(last|previous) month\b", value):
        prev = today.replace(day=1) - relativedelta(months=1)
        start, end = month_bounds(prev.year, prev.month)
        return DateRange(start, end, "last month", explicit=True)

    # Date ranges like 6/1/2026 to 6/15/2026 or June 1, 2026 - June 15, 2026.
    range_match = re.search(r"(.+?)\s+(?:to|through|thru|-)\s+(.+)", text, re.IGNORECASE)
    if range_match:
        try:
            start = parse_date(range_match.group(1), fuzzy=True, default=today).date()
            end = parse_date(range_match.group(2), fuzzy=True, default=today).date()
            if start > end:
                start, end = end, start
            return DateRange(start, end, f"{start.isoformat()} to {end.isoformat()}", explicit=True)
        except (ValueError, OverflowError):
            pass

    for month_name, month in MONTHS.items():
        pattern = rf"\b{re.escape(month_name)}\b(?:\s+(\d{{4}}))?"
        match = re.search(pattern, value)
        if match:
            year = int(match.group(1)) if match.group(1) else today.year
            if not match.group(1) and month > today.month:
                year -= 1
            start, end = month_bounds(year, month)
            return DateRange(start, min(end, today) if year == today.year and month == today.month else end, f"{calendar.month_name[month]} {year}", explicit=True)

    # Single explicit date.
    if re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", value):
        try:
            day = parse_date(text, fuzzy=True, default=today).date()
            return DateRange(day, day, day.isoformat(), explicit=True)
        except (ValueError, OverflowError):
            pass

    return default_month_to_date(today)
