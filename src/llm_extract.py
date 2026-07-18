"""
Extract structured transactions from bank-statement text using the Gemini API.

What Gemini receives from OCR — raw unstructured plain text containing everything:
  Bank Statement November 2019
  Account Number 12345678
  Date Description Amount
  01 Nov 19 TESCO STORES -62.40
  Opening Balance 1200.00
  Closing Balance 1122.61

What Gemini reads from that text:
  - date        e.g. "01 Nov 19"         (reads the date pattern on each line)
  - iso_date    e.g. "2019-11-01"        (infers full year from the statement header)
  - description e.g. "TESCO STORES"     (reads the merchant name)
  - amount      e.g. "-62.40"           (negative = debit, positive = credit)
  - currency    e.g. "GBP"              (infers from £/$/€ symbol or explicit text)

What Gemini ignores:
  - column headers (Date Description Amount)
  - statement headers (Bank Statement November 2019)
  - running totals, opening/closing balances
"""
from __future__ import annotations

from decimal import Decimal

from google import genai
from google.genai import types
from pydantic import BaseModel

from .parse import Transaction

MODEL = "gemini-2.5-flash"

"""
The system prompt is sent to Gemini before the OCR text. It tells Gemini exactly
what to extract and what to ignore — without this, Gemini might treat column headers
("Date Description Amount") or closing balances as real transactions.
"""
SYSTEM_PROMPT = (
    "You extract transaction line items from OCR'd bank statement text. "
    "Return every individual transaction (not section headers, column headers, "
    "running totals, or summary lines) with its date, description, and signed amount. "
    "Use a negative amount for debits/payments/withdrawals and a positive amount for "
    "credits/deposits. Also report the statement's currency as an ISO 4217 code "
    "(e.g. GBP, USD, EUR), inferring it from symbols like £/$/€ or any explicit text. "
    "For each transaction also resolve its date to ISO 8601 (YYYY-MM-DD) in 'iso_date', "
    "using the statement's year/period (e.g. from the statement header or surrounding "
    "context) to fill in any year or partial date that isn't explicit on the line itself."
)


"""
A class is a blueprint — it defines the shape of an object before any real data exists.
Like a form template: it says what fields must be filled in, but contains no values yet.
Gemini fills in one copy of this form per transaction found.

class 就像一张空白表格（模板）— 规定了有哪些栏位，但还没有填入真实数据。
就像银行的交易记录表：表格本身不是一笔交易，但每笔交易都按照这张表格填写。
Gemini 每找到一笔交易，就按这个模板填入真实的日期、描述和金额。

Why we use Pydantic:
  Data from outside your code (APIs, AI models) cannot be trusted to be in the right
  format. Pydantic validates it automatically and raises a clear error if something
  is wrong — instead of crashing mysteriously later in your code.

These Pydantic classes do two jobs in this file:
  Job 1 — Blueprint sent to Gemini: passed as response_schema=ExtractionResult,
           Pydantic converts these classes into a JSON schema that tells Gemini
           exactly what fields to include in its response.
  Job 2 — Parse Gemini's response: response.parsed automatically converts the raw
           JSON reply into a typed Python object — no manual json.loads() needed.
"""
class TransactionItem(BaseModel):
    """One transaction returned by Gemini — maps directly to the Transaction dataclass in parse.py."""
    date: str         # date as printed on the statement e.g. "01 Nov 19"
    iso_date: str     # resolved full date e.g. "2019-11-01", used for date-range filtering
    description: str  # merchant name e.g. "TESCO STORES"
    amount: str       # signed decimal string — negative = debit e.g. "-62.40", positive = credit


class ExtractionResult(BaseModel):
    """Top-level response from Gemini — contains the currency and all extracted transactions."""
    currency: str                      # ISO 4217 currency code e.g. "GBP", "USD"
    transactions: list[TransactionItem]  # list of all transactions Gemini found


def extract_transactions_llm(
    text: str, client: genai.Client | None = None,
) -> tuple[str, list[Transaction]]:
    """
    'text' is created by result_to_text() in ocr_advanced.py and passed here
    via pipeline.py. It is a newline-separated plain text string where each line
    is one line of text OCR read from the bank statement page.
    OCR produced it by rendering each PDF page into a pixel image, running
    Detection (locates text regions) and Recognition (reads text in each region),
    dropping low-confidence words, and joining everything with \n.
    That plain text arrives here as 'text' and is sent to Gemini as 'contents=text'.
    """
    # genai.Client() reads GEMINI_API_KEY / GOOGLE_API_KEY from the environment.
    client = client or genai.Client()

    """
    Gemini runs on Google's servers, so its response travels over the internet as text.
    Python tuples and objects cannot travel over a network — only text formats can.
    We use JSON because it is structured text that code can reliably read and parse.
      response_mime_type="application/json" — tells Gemini to reply in JSON, not plain sentences like:
        "On 6th November 2019, there was a payment to ARRIVA for £100.36."
        Code cannot reliably extract date/amount/description from prose — every sentence is written differently.
      response_schema=ExtractionResult     — tells Gemini exactly what fields to include
    After receiving the JSON, response.parsed converts it into a Python object automatically.
    """
    response = client.models.generate_content(
        model=MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
        ),
    )

    # SDK auto-parses the JSON response into our Pydantic model.
    result: ExtractionResult = response.parsed

    # Convert each LLM-extracted item into the shared Transaction dataclass.
    transactions = [
        Transaction(
            date=item.date,
            iso_date=item.iso_date,
            description=item.description,
            amount=Decimal(item.amount),
            raw_line="",  # no single source line; this came from a full-text LLM pass
        )
        for item in result.transactions
    ]
    return result.currency.upper(), transactions
