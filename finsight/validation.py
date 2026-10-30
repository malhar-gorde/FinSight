"""Input validation shared by the UI and the database layer.

Every validator either returns a cleaned dictionary of values or raises
``ValidationError`` with a message that is safe to show to the user.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime

from finsight.constants import (
    CATEGORIES_BY_TYPE,
    EXPENSE_CATEGORIES,
    INVESTMENT_CATEGORIES,
    MAX_AMOUNT,
    MAX_DESCRIPTION_LENGTH,
    MAX_NOTES_LENGTH,
    PAYMENT_METHODS,
    TRANSACTION_TYPES,
    VALUATION_FIXED,
    VALUATION_UNITS,
)

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ValidationError(ValueError):
    """Raised when user-supplied data is invalid."""


def to_iso_date(value, field: str = "Date") -> str:
    """Convert a date, datetime or ISO string into 'YYYY-MM-DD'."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10]).isoformat()
        except ValueError as exc:
            raise ValidationError(f"{field} must be a valid date (YYYY-MM-DD).") from exc
    raise ValidationError(f"{field} is required.")


def validate_amount(
    value, field: str = "Amount", allow_zero: bool = False, decimals: int = 2
) -> float:
    """Ensure an amount is a finite number that is positive (or zero if allowed)."""
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number.") from exc
    if math.isnan(amount) or math.isinf(amount):
        raise ValidationError(f"{field} must be a number.")
    if allow_zero:
        if amount < 0:
            raise ValidationError(f"{field} cannot be negative.")
    elif amount <= 0:
        raise ValidationError(f"{field} must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise ValidationError(f"{field} looks too large. Please check the value.")
    return round(amount, decimals)


def validate_month(value) -> str:
    month = str(value or "").strip()
    if not MONTH_PATTERN.match(month):
        raise ValidationError("Month must be in YYYY-MM format.")
    return month


def _clean_text(value, field: str, max_length: int, required: bool) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field} must be {max_length} characters or fewer.")
    return text


def validate_transaction(
    txn_date,
    description,
    category,
    txn_type,
    amount,
    payment_method,
    notes="",
    allow_future: bool = False,
) -> dict:
    if txn_type not in TRANSACTION_TYPES:
        raise ValidationError("Transaction type must be Income or Expense.")
    iso_date = to_iso_date(txn_date)
    if not allow_future and date.fromisoformat(iso_date) > date.today():
        raise ValidationError("Transaction date cannot be in the future.")
    if category not in CATEGORIES_BY_TYPE[txn_type]:
        raise ValidationError(f"'{category}' is not a valid {txn_type.lower()} category.")
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError("Please choose a valid payment method.")
    return {
        "date": iso_date,
        "description": _clean_text(description, "Description", MAX_DESCRIPTION_LENGTH, True),
        "category": category,
        "type": txn_type,
        "amount": validate_amount(amount),
        "payment_method": payment_method,
        "notes": _clean_text(notes, "Notes", MAX_NOTES_LENGTH, False),
    }


def validate_budget(month, category, amount) -> dict:
    if category not in EXPENSE_CATEGORIES:
        raise ValidationError("Budgets can only be created for expense categories.")
    return {
        "month": validate_month(month),
        "category": category,
        "amount": validate_amount(amount, "Budget limit"),
    }


def validate_goal(name, target_amount, target_date=None, description="") -> dict:
    return {
        "name": _clean_text(name, "Goal name", 80, True),
        "target_amount": validate_amount(target_amount, "Target amount"),
        "target_date": to_iso_date(target_date, "Target date") if target_date else None,
        "description": _clean_text(description, "Description", MAX_NOTES_LENGTH, False),
    }


def validate_investment(
    name,
    category,
    valuation_mode,
    purchase_date,
    quantity=None,
    purchase_price=None,
    current_price=None,
    invested_amount=None,
    current_value=None,
    notes="",
) -> dict:
    if category not in INVESTMENT_CATEGORIES:
        raise ValidationError("Please choose a valid asset category.")
    iso_date = to_iso_date(purchase_date, "Purchase date")
    if date.fromisoformat(iso_date) > date.today():
        raise ValidationError("Purchase date cannot be in the future.")

    cleaned = {
        "name": _clean_text(name, "Asset name", 80, True),
        "category": category,
        "valuation_mode": valuation_mode,
        "purchase_date": iso_date,
        "notes": _clean_text(notes, "Notes", MAX_NOTES_LENGTH, False),
        "quantity": None,
        "purchase_price": None,
        "current_price": None,
        "invested_amount": None,
        "current_value": None,
    }
    if valuation_mode == VALUATION_UNITS:
        cleaned["quantity"] = validate_amount(quantity, "Quantity / units", decimals=4)
        cleaned["purchase_price"] = validate_amount(purchase_price, "Purchase price")
        cleaned["current_price"] = validate_amount(current_price, "Current price", allow_zero=True)
    elif valuation_mode == VALUATION_FIXED:
        cleaned["invested_amount"] = validate_amount(invested_amount, "Amount invested")
        cleaned["current_value"] = validate_amount(current_value, "Current value", allow_zero=True)
    else:
        raise ValidationError("Unknown valuation mode.")
    return cleaned
