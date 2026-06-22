"""Write transactions out to CSV and JSON."""
from __future__ import annotations

import csv
import json

from .parse import Transaction


def write_csv(transactions: list[Transaction], path: str) -> None:
    # date,description,amount rows; amount kept as a string to preserve exact decimals.
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "description", "amount"])
        for t in transactions:
            writer.writerow([t.date, t.description, str(t.amount)])


def write_json(transactions: list[Transaction], path: str) -> None:
    # Same fields as write_csv, as a list of dicts (amount stringified for JSON safety).
    data = [
        {"date": t.date, "description": t.description, "amount": str(t.amount)}
        for t in transactions
    ]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
