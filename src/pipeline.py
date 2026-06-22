"""Extract transactions from a bank statement PDF: docTR OCR -> Gemini extraction."""
from __future__ import annotations

from .llm_extract import extract_transactions_llm
from .ocr_advanced import result_to_text, run_ocr
from .parse import Transaction


def extract_transactions(pdf_path: str) -> list[Transaction]:
    # 1. OCR the PDF with docTR (handles both scanned and digital PDFs).
    result = run_ocr(pdf_path)
    # 2. Flatten OCR output to plain text in reading order.
    text = result_to_text(result)
    # 3. Ask Gemini to pull structured transactions out of that text.
    return extract_transactions_llm(text)
