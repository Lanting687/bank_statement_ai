"""
Transaction dataclass — the shared data structure used by every file in the project.

Defined here once so every file uses the same structure instead of their own format.
You can tell which structure each file uses by reading its type hints:
  llm_extract.py  -> tuple[str, list[Transaction]]  (tuple: always returns currency + transactions together)
  pipeline.py     -> tuple[str, list[Transaction]]  (tuple: always returns currency + transactions together)
  filter.py       -> list[Transaction]              (list: number of transactions varies after filtering)
  export.py       -> list[Transaction]              (list: number of transactions to write varies)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Transaction:
    date: str           # as printed on the statement (no normalization)
    description: str    # merchant / payee text
    amount: Decimal      # signed: negative = money out, positive = money in
    raw_line: str        # original OCR'd line this was parsed from, if any
    iso_date: str = ""   # resolved YYYY-MM-DD, for date-range filtering (LLM-extracted only)

    @property
    def is_debit(self) -> bool:
        # Negative amount means a debit (payment/withdrawal).
        return self.amount < 0
