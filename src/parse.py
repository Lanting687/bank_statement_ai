"""Transaction record shared by extraction, filtering, and export."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Transaction:
    date: str          # as printed on the statement (no normalization)
    description: str   # merchant / payee text
    amount: Decimal     # signed: negative = money out, positive = money in
    raw_line: str       # original OCR'd line this was parsed from, if any

    @property
    def is_debit(self) -> bool:
        # Negative amount means a debit (payment/withdrawal).
        return self.amount < 0
