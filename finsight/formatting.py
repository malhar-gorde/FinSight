"""Display formatting for currency, percentages, dates and months."""

from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd

EMPTY = "—"


def _indian_grouping(integer_digits: str) -> str:
    """Group digits the Indian way: 1,25,00,000."""
    if len(integer_digits) <= 3:
        return integer_digits
    last_three = integer_digits[-3:]
    rest = integer_digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join(groups + [last_three])


def format_inr(value, decimals: int = 0, show_sign: bool = False) -> str:
    """Format a number as Indian rupees, e.g. 125000 -> '₹1,25,000'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return EMPTY
    amount = float(value)
    negative = amount < 0
    rounded = f"{abs(amount):.{decimals}f}"
    if decimals > 0:
        integer_part, fraction = rounded.split(".")
        body = f"{_indian_grouping(integer_part)}.{fraction}"
    else:
        body = _indian_grouping(rounded)
    if negative and float(rounded) != 0:
        return f"−₹{body}"
    if show_sign and float(rounded) != 0:
        return f"+₹{body}"
    return f"₹{body}"


def format_compact_inr(value) -> str:
    """Short form for chart axes and tight spaces: ₹1.2L, ₹3.4Cr, ₹12.5K."""
    if value is None:
        return EMPTY
    amount = float(value)
    sign = "−" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1e7:
        return f"{sign}₹{amount / 1e7:.2f}Cr"
    if amount >= 1e5:
        return f"{sign}₹{amount / 1e5:.2f}L"
    if amount >= 1e3:
        return f"{sign}₹{amount / 1e3:.1f}K"
    return f"{sign}₹{amount:.0f}"


def format_pct(value, decimals: int = 1, show_sign: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return EMPTY
    sign = "+" if show_sign and value > 0 else ""
    text = f"{sign}{value:.{decimals}f}%"
    return text.replace("-", "−")


def format_date(value) -> str:
    """'2026-10-05' -> '05 Oct 2026'."""
    if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
        return EMPTY
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    if isinstance(value, (pd.Timestamp, datetime)):
        value = value.date()
    return value.strftime("%d %b %Y")


def month_label(month: str, short: bool = False) -> str:
    """'2026-10' -> 'October 2026' (or 'Oct 2026' when short)."""
    year, mon = month.split("-")
    first = date(int(year), int(mon), 1)
    return first.strftime("%b %Y" if short else "%B %Y")


def format_quantity(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return EMPTY
    text = f"{float(value):,.4f}".rstrip("0").rstrip(".")
    return text
