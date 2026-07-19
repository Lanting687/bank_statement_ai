from decimal import Decimal

from src import fx


# --- fx.convert ---
# Checks currency conversion behaviour including edge cases and failure handling.

def test_same_currency_short_circuits_without_request(monkeypatch):
    # Converting GBP → GBP should return the original amount without any HTTP call
    def _raise_if_called(*args, **kwargs):
        raise AssertionError("should not have been called")

    monkeypatch.setattr(fx.requests, "get", _raise_if_called)
    amount, warning = fx.convert(Decimal("100"), "GBP", "GBP")
    assert amount == Decimal("100")
    assert warning is None


def test_convert_applies_rate(monkeypatch):
    # With a rate of 1.25, £100 should become $125.00
    monkeypatch.setattr(fx, "get_rate", lambda f, t: Decimal("1.25"))
    amount, warning = fx.convert(Decimal("100"), "GBP", "USD")
    assert amount == Decimal("125.00")
    assert warning is None


def test_convert_falls_back_to_1to1_on_failure(monkeypatch):
    # If the FX API is unreachable, fall back to 1:1 and return a warning instead of crashing
    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(fx, "get_rate", _raise)
    amount, warning = fx.convert(Decimal("100"), "GBP", "USD")
    assert amount == Decimal("100")
    assert warning is not None


def test_convert_preserves_sign_on_negative_amounts(monkeypatch):
    # Debits are negative — conversion should preserve the sign (e.g. -£100 → -$125)
    monkeypatch.setattr(fx, "get_rate", lambda *_: Decimal("1.25"))
    amount, warning = fx.convert(Decimal("-100"), "GBP", "USD")
    assert amount == Decimal("-125.00")
    assert warning is None
