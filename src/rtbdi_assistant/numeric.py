from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation

TOTAL_MARKERS = ("total", "subtotal", "grand total")


def is_total_row(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().casefold()
    return any(marker == text or text.endswith(f" {marker}") for marker in TOTAL_MARKERS)


def parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace("$", "").replace(",", "").replace("%", "").strip()
    if not re.search(r"\d", text):
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def parse_percent(value: object) -> Decimal | None:
    parsed = parse_decimal(value)
    if parsed is None:
        return None
    return parsed / Decimal(100)
