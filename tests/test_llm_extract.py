import json
from decimal import Decimal

from src import llm_extract


# --- llm_extract.extract_transactions_llm ---
# Checks DeepSeek request construction and response parsing. No real network
# calls are made -- requests.post is monkeypatched, matching the pattern in
# tests/test_fx.py.

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _chat_completion(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_sends_bearer_token_and_configured_base_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/v1")

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(_chat_completion({"currency": "GBP", "transactions": []}))

    monkeypatch.setattr(llm_extract.requests, "post", _fake_post)

    llm_extract.extract_transactions_llm("some ocr text")

    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-key"
    assert captured["json"]["model"] == llm_extract.MODEL
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_defaults_to_public_deepseek_url_when_unset(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.delenv("DEEPSEEK_API_URL", raising=False)

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(_chat_completion({"currency": "GBP", "transactions": []}))

    monkeypatch.setattr(llm_extract.requests, "post", _fake_post)

    llm_extract.extract_transactions_llm("some ocr text")

    assert captured["url"] == f"{llm_extract.DEFAULT_BASE_URL}/chat/completions"


def test_parses_transactions_and_preserves_signed_amounts(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")

    payload = _chat_completion({
        "currency": "gbp",
        "transactions": [
            {
                "date": "01 Nov 19", "iso_date": "2019-11-01",
                "description": "TESCO STORES", "amount": "-62.40",
            },
            {
                "date": "02 Nov 19", "iso_date": "2019-11-02",
                "description": "SALARY", "amount": "1500.00",
            },
        ],
    })

    monkeypatch.setattr(
        llm_extract.requests, "post",
        lambda *a, **kw: _FakeResponse(payload),
    )

    currency, transactions = llm_extract.extract_transactions_llm("some ocr text")

    assert currency == "GBP"  # normalised to uppercase
    assert len(transactions) == 2
    assert transactions[0].description == "TESCO STORES"
    assert transactions[0].amount == Decimal("-62.40")
    assert transactions[1].amount == Decimal("1500.00")
