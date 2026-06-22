"""Extract structured transactions from bank-statement text using the Claude API."""
from __future__ import annotations

import json
from decimal import Decimal

import anthropic

from .parse import Transaction

MODEL = "claude-opus-4-8"

TRANSACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Transaction date, as printed on the statement"},
                    "description": {"type": "string", "description": "Transaction description/merchant, as printed"},
                    "amount": {
                        "type": "string",
                        "description": (
                            "Signed decimal amount, e.g. '-15.60' or '2000.00'. "
                            "Negative for debits/payments/withdrawals, positive for credits/deposits."
                        ),
                    },
                },
                "required": ["date", "description", "amount"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["transactions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You extract transaction line items from OCR'd bank statement text. "
    "Return every individual transaction (not section headers, column headers, "
    "running totals, or summary lines) with its date, description, and signed amount. "
    "Use a negative amount for debits/payments/withdrawals and a positive amount for "
    "credits/deposits."
)


def extract_transactions_llm(text: str, client: anthropic.Anthropic | None = None) -> list[Transaction]:
    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": TRANSACTION_SCHEMA}},
        messages=[{"role": "user", "content": text}],
    )

    raw = next(block.text for block in response.content if block.type == "text")
    data = json.loads(raw)

    return [
        Transaction(
            date=item["date"],
            description=item["description"],
            amount=Decimal(item["amount"]),
            raw_line="",
        )
        for item in data["transactions"]
    ]
