"""Extract transactions from a bank statement PDF: docTR OCR -> Claude extraction."""
from __future__ import annotations

from .llm_extract import extract_transactions_llm
from .ocr_advanced import result_to_text, run_ocr
from .parse import Transaction


def extract_transactions(pdf_path: str) -> list[Transaction]:
    result = run_ocr(pdf_path)
    text = result_to_text(result)
    return extract_transactions_llm(text)
