from datetime import date

from rtbdi_assistant.dates import resolve_date_range


def test_default_is_month_to_date():
    resolved = resolve_date_range("How many boxes did we sell?", today=date(2026, 6, 21))
    assert resolved.start == date(2026, 6, 1)
    assert resolved.end == date(2026, 6, 21)
    assert resolved.explicit is False


def test_last_month():
    resolved = resolve_date_range("accessories last month", today=date(2026, 6, 21))
    assert resolved.start == date(2026, 5, 1)
    assert resolved.end == date(2026, 5, 31)


def test_last_days_is_inclusive():
    resolved = resolve_date_range("last 7 days", today=date(2026, 6, 21))
    assert resolved.start == date(2026, 6, 15)
    assert resolved.end == date(2026, 6, 21)


def test_year_to_date():
    resolved = resolve_date_range("year-to-date total activations", today=date(2026, 6, 21))
    assert resolved.start == date(2026, 1, 1)
    assert resolved.end == date(2026, 6, 21)
    assert resolved.label == "year-to-date"
