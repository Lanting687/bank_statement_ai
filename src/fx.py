"""Currency conversion via the free, keyless Frankfurter FX API."""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import requests

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


@lru_cache(maxsize=64)
def get_rate(from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return Decimal("1")

    response = requests.get(
        FRANKFURTER_URL,
        params={"from": from_currency, "to": to_currency},
        timeout=10,
    )
    response.raise_for_status()
    rate = response.json()["rates"][to_currency]
    return Decimal(str(rate))


def convert(amount: Decimal, from_currency: str, to_currency: str) -> tuple[Decimal, str | None]:
    """Convert amount, returning (converted_amount, warning).

    Falls back to a 1:1 rate (with a warning message) if the FX lookup fails,
    rather than breaking the whole extraction for one bad/unsupported code.
    """
    try:
        rate = get_rate(from_currency, to_currency)
    except Exception:
        return amount, f"FX lookup failed for {from_currency}->{to_currency}; showing original amounts"
    return amount * rate, None
