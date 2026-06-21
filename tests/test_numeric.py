from decimal import Decimal

from rtbdi_assistant.numeric import is_total_row, parse_decimal, parse_percent


def test_parse_currency_and_accounting_negative():
    assert parse_decimal("$9,953.14") == Decimal("9953.14")
    assert parse_decimal("($12.25)") == Decimal("-12.25")


def test_parse_percent():
    assert parse_percent("97.3%") == Decimal("0.973")


def test_total_row_detection():
    assert is_total_row("Grand Total")
    assert is_total_row("Store Subtotal")
    assert not is_total_row("ROCKON MAIN")
