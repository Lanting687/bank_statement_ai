from decimal import Decimal

from src.parse import Transaction


def _txn(amount: str) -> Transaction:
    return Transaction(date="01/01/2026", description="x", amount=Decimal(amount), raw_line="")


def test_negative_amount_is_debit():
    assert _txn("-0.01").is_debit is True


def test_positive_amount_is_not_debit():
    assert _txn("0.01").is_debit is False


def test_zero_amount_is_not_debit():
    assert _txn("0").is_debit is False
