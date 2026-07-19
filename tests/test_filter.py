from decimal import Decimal

from src.filter import filter_payments, in_date_range
from src.parse import Transaction


def _txn(amount: str) -> Transaction:
    return Transaction(date="01/01/2026", description="x", amount=Decimal(amount), raw_line="")


# --- filter_payments ---
# Checks that only debit transactions at or above the threshold are kept.

def test_keeps_only_debits_at_or_above_threshold():
    # -500 and -1000 pass; -499.99 is below threshold; +500 is a credit
    transactions = [_txn("-500.00"), _txn("-499.99"), _txn("500.00"), _txn("-1000.00")]
    result = filter_payments(transactions, Decimal("500"))
    assert [t.amount for t in result] == [Decimal("-500.00"), Decimal("-1000.00")]


def test_empty_list_returns_empty():
    # No transactions in → no transactions out
    assert filter_payments([], Decimal("0")) == []


def test_all_credits_excluded():
    # Positive amounts are credits and should never appear in the result
    transactions = [_txn("100.00"), _txn("200.00")]
    assert filter_payments(transactions, Decimal("0")) == []


def test_threshold_zero_keeps_all_debits():
    # Threshold of 0 means every debit qualifies, no matter how small
    transactions = [_txn("-0.01"), _txn("-999.99")]
    result = filter_payments(transactions, Decimal("0"))
    assert len(result) == 2


def test_boundary_amount_is_included():
    # A debit exactly equal to the threshold should be included, not excluded
    result = filter_payments([_txn("-500.00")], Decimal("500"))
    assert len(result) == 1


# --- in_date_range ---
# Checks that the date filter includes/excludes rows correctly.

def test_date_within_range():
    # A date that falls inside the range should be included
    assert in_date_range("2019-11-06", "2019-11-01", "2019-11-30") is True


def test_date_before_range():
    # A date before the start of the range should be excluded
    assert in_date_range("2019-10-31", "2019-11-01", "2019-11-30") is False


def test_date_after_range():
    # A date after the end of the range should be excluded
    assert in_date_range("2019-12-01", "2019-11-01", "2019-11-30") is False


def test_blank_date_always_included():
    # If Gemini couldn't resolve a date, the row should not be silently dropped
    assert in_date_range("", "2019-11-01", "2019-11-30") is True


def test_no_start_date_allows_early_dates():
    # No start date means no lower bound — any early date should pass
    assert in_date_range("2019-01-01", None, "2019-11-30") is True


def test_no_end_date_allows_late_dates():
    # No end date means no upper bound — any late date should pass
    assert in_date_range("2099-12-31", "2019-11-01", None) is True


def test_no_range_always_included():
    # No start and no end means show everything
    assert in_date_range("2019-11-06", None, None) is True
