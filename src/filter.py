"""Filter transactions down to payments (debits) at or above a threshold."""
from __future__ import annotations

from decimal import Decimal

from .parse import Transaction


def filter_payments(transactions: list[Transaction], threshold: Decimal) -> list[Transaction]:
    return [t for t in transactions if t.is_debit and -t.amount >= threshold]
