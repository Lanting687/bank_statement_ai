"""Transaction record shared by extraction, filtering, and export."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Transaction:
    date: str
    description: str
    amount: Decimal
    raw_line: str

    @property
    def is_debit(self) -> bool:
        return self.amount < 0
