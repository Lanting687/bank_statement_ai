from decimal import Decimal

from src.filter import filter_payments
from src.parse import Transaction


def _txn(amount: str) -> Transaction:
    return Transaction(date="01/01/2026", description="x", amount=Decimal(amount), raw_line="")


def test_keeps_only_debits_at_or_above_threshold():
    transactions = [_txn("-500.00"), _txn("-499.99"), _txn("500.00"), _txn("-1000.00")]
    result = filter_payments(transactions, Decimal("500"))
    assert [t.amount for t in result] == [Decimal("-500.00"), Decimal("-1000.00")]
