"""
PDF handling for the review workspace: decode an uploaded PDF, validate it,
and render individual pages as images for the browser — all in memory, with
nothing written to disk and no server filesystem path ever handed to the
browser.

Rendering is done with pypdfium2 rather than a new heavyweight dependency.
python-doctr already depends on pypdfium2 to rasterise PDF pages for OCR
(see ocr_advanced.run_ocr, which calls doctr.io.DocumentFile.from_pdf), so
using it here for the review-panel preview adds no new install weight.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
from dataclasses import dataclass

import pypdfium2 as pdfium

DEFAULT_RENDER_DPI = 120


class PDFReviewError(Exception):
    """Base class for review-workspace PDF errors.

    Callers (the Dash app) catch this to show a clean, user-facing message
    instead of a raw traceback — see app.py's upload/render callbacks and
    docs/ARCHITECTURE.md section 5.7 (error handling).
    """


class InvalidPDFError(PDFReviewError):
    """Raised for content that isn't a readable PDF: corrupt, empty, wrong
    file type, or malformed upload encoding."""


class PasswordProtectedPDFError(PDFReviewError):
    """Raised when the PDF exists and is well-formed but requires a
    password we don't have. We don't prompt for passwords in this
    prototype — the user needs to upload a decrypted copy."""


class PageOutOfRangeError(PDFReviewError):
    """Raised when a requested page number isn't in the document.

    The Dash layer is expected to clamp navigation before this ever fires,
    but importable/raisable directly is useful for tests and defensive
    callback code.
    """


@dataclass(frozen=True)
class PDFDocument:
    """An uploaded PDF, decoded and validated, ready to be rendered.

    `pdf_bytes` lives only in memory / in Dash's serialized store data for
    the lifetime of the browser session — never written to a shared or
    permanent directory. `document_id` is a content hash, not a filesystem
    path, so it's safe to expose to the browser (e.g. as part of a
    pattern-matching component id) without leaking anything about the
    server's disk layout.
    """

    document_id: str
    filename: str
    pdf_bytes: bytes
    page_count: int


def decode_upload(contents: str) -> bytes:
    """Decode a Dash dcc.Upload `contents` string into raw PDF bytes.

    `contents` looks like "data:application/pdf;base64,<data>". Raises
    InvalidPDFError for anything that isn't that shape or isn't valid
    base64 — callers should not assume the browser always sends
    well-formed data.
    """
    if not contents or "," not in contents:
        raise InvalidPDFError("Upload did not contain PDF data.")
    _header, _, b64_data = contents.partition(",")
    try:
        return base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidPDFError(f"Upload could not be decoded: {exc}") from exc


def make_document_id(pdf_bytes: bytes) -> str:
    """Stable, content-addressed id for an uploaded PDF.

    Hashing the bytes (rather than using the filename or a random uuid)
    means re-uploading the same file always gets the same id, and the id
    itself reveals nothing about the original filename or any server path.
    Truncated to 16 hex chars — plenty of collision resistance for a
    single-session review workspace, and short enough to use as a Dash
    component id.
    """
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]


def _open(pdf_bytes: bytes) -> pdfium.PdfDocument:
    """Open pdf_bytes with pypdfium2, translating its errors into the
    typed errors this module exposes."""
    if not pdf_bytes:
        raise InvalidPDFError("Uploaded file is empty.")
    try:
        return pdfium.PdfDocument(pdf_bytes)
    except pdfium.PdfiumError as exc:
        message = str(exc)
        if "password" in message.lower():
            raise PasswordProtectedPDFError(
                "This PDF is password-protected. Upload a decrypted copy to review it."
            ) from exc
        raise InvalidPDFError(f"Could not read this file as a PDF: {message}") from exc


def load_document(filename: str, pdf_bytes: bytes) -> PDFDocument:
    """Validate an uploaded PDF and return a PDFDocument ready for review.

    This is the single entry point the Dash app should call right after
    decode_upload(): it fails fast (with a typed, user-facing error) on
    anything unreadable, rather than letting a bad upload surface later as
    an obscure OCR or rendering failure.
    """
    pdf = _open(pdf_bytes)
    try:
        page_count = len(pdf)
    finally:
        pdf.close()

    if page_count == 0:
        raise InvalidPDFError("PDF has no pages.")

    return PDFDocument(
        document_id=make_document_id(pdf_bytes),
        filename=filename,
        pdf_bytes=pdf_bytes,
        page_count=page_count,
    )


def render_page_png_base64(
    pdf_bytes: bytes, page_number: int, dpi: int = DEFAULT_RENDER_DPI
) -> str:
    """Render one page (1-indexed) of pdf_bytes to a base64-encoded PNG.

    Returns the raw base64 string (no data-URI prefix) so callers decide
    how to use it — the Dash app wraps it as
    f"data:image/png;base64,{result}" for an html.Img src. Nothing is
    written to disk: pypdfium2 renders straight from the in-memory bytes,
    and Pillow encodes the PNG straight to an in-memory buffer.
    """
    pdf = _open(pdf_bytes)
    try:
        if page_number < 1 or page_number > len(pdf):
            raise PageOutOfRangeError(
                f"Page {page_number} is out of range (document has {len(pdf)} pages)."
            )
        page = pdf[page_number - 1]
        try:
            bitmap = page.render(scale=dpi / 72)
            image = bitmap.to_pil()
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        finally:
            page.close()
    finally:
        pdf.close()
