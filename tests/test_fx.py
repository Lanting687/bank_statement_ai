from decimal import Decimal

from src import fx


def test_same_currency_short_circuits_without_request(monkeypatch):
    def _raise_if_called(*args, **kwargs):
        raise AssertionError("should not have been called")

    monkeypatch.setattr(fx.requests, "get", _raise_if_called)
    amount, warning = fx.convert(Decimal("100"), "GBP", "GBP")
    assert amount == Decimal("100")
    assert warning is None


def test_convert_applies_rate(monkeypatch):
    monkeypatch.setattr(fx, "get_rate", lambda f, t: Decimal("1.25"))
    amount, warning = fx.convert(Decimal("100"), "GBP", "USD")
    assert amount == Decimal("125.00")
    assert warning is None


def test_convert_falls_back_to_1to1_on_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(fx, "get_rate", _raise)
    amount, warning = fx.convert(Decimal("100"), "GBP", "USD")
    assert amount == Decimal("100")
    assert warning is not None
