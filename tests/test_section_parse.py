from decimal import Decimal

from src.section_parse import parse_section_text

STATEMENT = """
CHECKING SUMMARY
Beginning Balance $81,607.40
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
07/02 Deposit $17,120.00
07/09 Deposit 24,610.00
Total Deposits and Additions $41,730.00
CHECKS PAID
DATE
CHECK NUMBER DESCRIPTION PAID AMOUNT
XXXX ^ 07/14 $1,471.99
Total Checks Paid $1,471.99
OTHER WITHDRAWALS, FEES & CHARGES
DATE DESCRIPTION AMOUNT
07/11 Online Payment XXXXX To Vendor $8,928.00
Total Other Withdrawals, Fees & Charges $8,928.00
DAILY ENDING BALANCE
DATE AMOUNT DATE AMOUNT
07/02 $98,727.40 07/21 129,173.36
"""


def test_deposits_are_credits():
    transactions = parse_section_text(STATEMENT)
    deposits = [t for t in transactions if t.description == "Deposit"]
    assert {t.amount for t in deposits} == {Decimal("17120.00"), Decimal("24610.00")}
    assert all(not t.is_debit for t in deposits)


def test_checks_and_withdrawals_are_debits():
    transactions = parse_section_text(STATEMENT)
    debits = {t.description: t.amount for t in transactions if t.is_debit}
    assert debits["XXXX ^"] == Decimal("-1471.99")
    assert debits["Online Payment XXXXX To Vendor"] == Decimal("-8928.00")


def test_total_lines_and_daily_balance_section_are_not_transactions():
    transactions = parse_section_text(STATEMENT)
    assert len(transactions) == 4
    assert all("Total" not in t.description for t in transactions)
    assert not any(t.date == "07/21" for t in transactions)
