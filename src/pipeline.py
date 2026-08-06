"""
Connect ocr_advanced.py and llm_extract.py into one single entry point.

Without pipeline.py, every caller (the UI and the CLI) would have to repeat
the same steps themselves. Instead, callers use one of the functions below
and pipeline.py handles the connection between OCR and DeepSeek internally.

OCR and DeepSeek extraction are exposed as two separate steps
(run_ocr_only / extract_statement_from_ocr) as well as one combined call
(extract_statement). The review workspace in app.py needs OCR and DeepSeek
decoupled: OCR runs once when the user starts a review, its OCRResult is
cached and reused for both page-by-page review and (later) DeepSeek
extraction, so navigating pages or re-viewing a document never re-runs OCR
or calls DeepSeek again. The CLI doesn't need that split, so it still calls
extract_statement()/extract_transactions() exactly as before.
"""
from __future__ import annotations

from .llm_extract import extract_transactions_llm
from .models import OCRResult
from .ocr_advanced import extract_ocr
from .parse import Transaction


def run_ocr_only(pdf_path: str) -> OCRResult:
    """Run OCR and return the page-aware result, without calling DeepSeek.

    Used by the Dash review workspace's "Run OCR" step: the OCRResult it
    returns is cached (in a serializable form) and reused both for the
    side-by-side page review and, later, for extract_statement_from_ocr().
    """
    return extract_ocr(pdf_path)


def extract_statement_from_ocr(ocr_result: OCRResult) -> tuple[str, list[Transaction]]:
    """Run DeepSeek extraction against an already-computed OCRResult.

    Takes OCRResult rather than a path so this never re-runs OCR — the
    caller must have already run run_ocr_only() (or extract_statement()
    below, which does both steps itself).
    """
    return extract_transactions_llm(ocr_result.full_text)


def extract_statement(pdf_path: str) -> tuple[str, list[Transaction]]:
    """Returns (currency, transactions) for the given PDF.

    Full pipeline in one call: OCR then DeepSeek. Kept for the CLI and as a
    convenience for any caller that doesn't need the review workspace's
    two-step split.
    """
    ocr_result = run_ocr_only(pdf_path)
    return extract_statement_from_ocr(ocr_result)


def extract_transactions(pdf_path: str) -> list[Transaction]:
    _currency, transactions = extract_statement(pdf_path)
    return transactions
