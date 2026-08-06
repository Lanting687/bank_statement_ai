"""
Shared typed data models for OCR review.

Why this module exists: ocr_advanced.py used to hand back a single flattened
string (all pages concatenated). That is fine for Gemini (which just wants
the whole document as text) but it throws away page boundaries, so the
review workspace has nothing to align against the PDF page currently on
screen. OCRPage/OCRResult keep the per-page boundary while still exposing a
`full_text` property so every existing caller (Gemini extraction, the CLI)
keeps working unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OCRPage:
    """OCR output for a single PDF page.

    page_number is 1-indexed to match how pages are numbered in the review
    UI ("Page 1 of 6"), not 0-indexed like Python lists.
    """

    page_number: int
    text: str  # newline-separated recognised lines for this page; "" if none


@dataclass(frozen=True)
class OCRResult:
    """OCR output for an entire document, page by page.

    Built once per document (after the expensive docTR pass) and reused for
    both the page-by-page review panel and the combined text sent to Gemini,
    so OCR never has to run twice for the same file.
    """

    pages: tuple[OCRPage, ...]

    @property
    def full_text(self) -> str:
        """All pages flattened into one string, for Gemini and the CLI.

        Pages with no recognised text are skipped so this reproduces the
        exact string the old single-pass result_to_text() used to return
        (no blank-page placeholders, no double newlines).
        """
        return "\n".join(page.text for page in self.pages if page.text)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def page(self, page_number: int) -> OCRPage | None:
        """1-indexed page lookup. Returns None if out of range instead of
        raising, since the review UI needs to show an "unavailable" state
        rather than crash when navigation goes past what OCR returned."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None
