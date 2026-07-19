from decimal import Decimal

from src.filter import filter_payments, in_date_range
from src.parse import Transaction


def _txn(amount: str) -> Transaction:
    return Transaction(date="01/01/2026", description="x", amount=Decimal(amount), raw_line="")


# --- filter_payments ---

def test_keeps_only_debits_at_or_above_threshold():
    transactions = [_txn("-500.00"), _txn("-499.99"), _txn("500.00"), _txn("-1000.00")]
    result = filter_payments(transactions, Decimal("500"))
    assert [t.amount for t in result] == [Decimal("-500.00"), Decimal("-1000.00")]


def test_empty_list_returns_empty():
    assert filter_payments([], Decimal("0")) == []


def test_all_credits_excluded():
    transactions = [_txn("100.00"), _txn("200.00")]
    assert filter_payments(transactions, Decimal("0")) == []


def test_threshold_zero_keeps_all_debits():
    transactions = [_txn("-0.01"), _txn("-999.99")]
    result = filter_payments(transactions, Decimal("0"))
    assert len(result) == 2


def test_boundary_amount_is_included():
    result = filter_payments([_txn("-500.00")], Decimal("500"))
    assert len(result) == 1


# --- Transaction.is_debit ---

def test_negative_amount_is_debit():
    assert _txn("-0.01").is_debit is True


def test_positive_amount_is_not_debit():
    assert _txn("0.01").is_debit is False


def test_zero_amount_is_not_debit():
    assert _txn("0").is_debit is False


# --- in_date_range ---

def test_date_within_range():
    assert in_date_range("2019-11-06", "2019-11-01", "2019-11-30") is True


def test_date_before_range():
    assert in_date_range("2019-10-31", "2019-11-01", "2019-11-30") is False


def test_date_after_range():
    assert in_date_range("2019-12-01", "2019-11-01", "2019-11-30") is False


def test_blank_date_always_included():
    assert in_date_range("", "2019-11-01", "2019-11-30") is True


def test_no_start_date_allows_early_dates():
    assert in_date_range("2019-01-01", None, "2019-11-30") is True


def test_no_end_date_allows_late_dates():
    assert in_date_range("2099-12-31", "2019-11-01", None) is True


def test_no_range_always_included():
    assert in_date_range("2019-11-06", None, None) is True
