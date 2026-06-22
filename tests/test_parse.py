from decimal import Decimal

from src.parse import parse_transactions


def test_parses_debit_with_trailing_minus():
    text = "01/15/2026 GROCERY STORE PURCHASE 123.45- 4,876.55"
    [t] = parse_transactions(text)
    assert t.date == "01/15/2026"
    assert t.description == "GROCERY STORE PURCHASE"
    assert t.amount == Decimal("-123.45")
    assert t.is_debit


def test_parses_credit_positive_amount():
    text = "02/01/2026 PAYROLL DEPOSIT 2,500.00 7,376.55"
    [t] = parse_transactions(text)
    assert t.amount == Decimal("2500.00")
    assert not t.is_debit


def test_parses_amount_in_parentheses_as_negative():
    text = "03/03/2026 ATM WITHDRAWAL (60.00) 7,316.55"
    [t] = parse_transactions(text)
    assert t.amount == Decimal("-60.00")


def test_skips_lines_without_a_leading_date():
    text = "Statement period: 01/01/2026 - 01/31/2026\nBalance forward 100.00"
    assert parse_transactions(text) == []


def test_skips_dated_lines_without_an_amount():
    text = "01/15/2026 see attached note"
    assert parse_transactions(text) == []
