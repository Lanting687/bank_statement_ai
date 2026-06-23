"""Extract structured transactions from bank-statement text using the Gemini API."""
from __future__ import annotations

from decimal import Decimal

from google import genai
from google.genai import types
from pydantic import BaseModel

from .parse import Transaction

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You extract transaction line items from OCR'd bank statement text. "
    "Return every individual transaction (not section headers, column headers, "
    "running totals, or summary lines) with its date, description, and signed amount. "
    "Use a negative amount for debits/payments/withdrawals and a positive amount for "
    "credits/deposits. Also report the statement's currency as an ISO 4217 code "
    "(e.g. GBP, USD, EUR), inferring it from symbols like £/$/€ or any explicit text."
)


# Pydantic models double as the JSON schema Gemini is forced to respond with
# (passed via response_schema below) and as the parsed-response type.
class TransactionItem(BaseModel):
    date: str
    description: str
    amount: str  # signed decimal string, e.g. "-15.60" or "2000.00"


class ExtractionResult(BaseModel):
    currency: str  # ISO 4217 guess, e.g. "GBP", "USD"
    transactions: list[TransactionItem]


def extract_transactions_llm(
    text: str, client: genai.Client | None = None,
) -> tuple[str, list[Transaction]]:
    # genai.Client() reads GEMINI_API_KEY / GOOGLE_API_KEY from the environment.
    client = client or genai.Client()

    response = client.models.generate_content(
        model=MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionResult,  # forces/validates structured JSON output
        ),
    )

    # SDK auto-parses the JSON response into our Pydantic model.
    result: ExtractionResult = response.parsed

    # Convert each LLM-extracted item into the shared Transaction dataclass.
    transactions = [
        Transaction(
            date=item.date,
            description=item.description,
            amount=Decimal(item.amount),
            raw_line="",  # no single source line; this came from a full-text LLM pass
        )
        for item in result.transactions
    ]
    return result.currency.upper(), transactions
