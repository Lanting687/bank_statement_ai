"""
Connect ocr_advanced.py and llm_extract.py into one single entry point.

Without pipeline.py, every caller (the UI and the CLI) would have to repeat
the same three steps themselves. Instead, both callers just call extract_statement()
and pipeline.py handles the connection between OCR and Gemini internally.
"""
from __future__ import annotations

from .llm_extract import extract_transactions_llm
from .ocr_advanced import result_to_text, run_ocr
from .parse import Transaction


def extract_statement(pdf_path: str) -> tuple[str, list[Transaction]]:
    """Returns (currency, transactions) for the given PDF."""
    # 1. Run OCR — result is the Document tree (pages -> blocks -> lines -> words)
    #    created and returned by run_ocr() in ocr_advanced.py.
    result = run_ocr(pdf_path)
    # 2. Flatten result into plain text — text is created here by result_to_text()
    #    in ocr_advanced.py and stored in this variable before being passed to Gemini.
    text = result_to_text(result)
    # 3. Send text to Gemini — extract_transactions_llm() in llm_extract.py receives
    #    text and returns structured (currency, transactions).
    return extract_transactions_llm(text)


def extract_transactions(pdf_path: str) -> list[Transaction]:
    _currency, transactions = extract_statement(pdf_path)
    return transactions
