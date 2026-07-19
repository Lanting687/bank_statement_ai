from decimal import Decimal

from src.parse import Transaction


def _txn(amount: str) -> Transaction:
    return Transaction(date="01/01/2026", description="x", amount=Decimal(amount), raw_line="")


# --- Transaction.is_debit ---
# Checks that the is_debit property correctly identifies payments out.

def test_negative_amount_is_debit():
    # Negative amount means money went out — should be flagged as a debit
    assert _txn("-0.01").is_debit is True


def test_positive_amount_is_not_debit():
    # Positive amount means money came in — should not be flagged as a debit
    assert _txn("0.01").is_debit is False


def test_zero_amount_is_not_debit():
    # Zero is not a payment out
    assert _txn("0").is_debit is False
