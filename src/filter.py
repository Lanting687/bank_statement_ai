"""Filter transactions down to payments (debits) at or above a threshold."""
from __future__ import annotations

from decimal import Decimal

from .parse import Transaction


def filter_payments(transactions: list[Transaction], threshold: Decimal) -> list[Transaction]:
    # Keep debits only, and only those whose absolute value clears the threshold.
    return [t for t in transactions if t.is_debit and -t.amount >= threshold]


def in_date_range(iso_date: str, start_date: str | None, end_date: str | None) -> bool:
    # ISO 8601 (YYYY-MM-DD) strings compare correctly lexicographically.
    # If Gemini couldn't resolve a date, don't exclude the row silently.
    if not iso_date or len(iso_date) != 10:
        return True
    if start_date and iso_date < start_date:
        return False
    if end_date and iso_date > end_date:
        return False
    return True
