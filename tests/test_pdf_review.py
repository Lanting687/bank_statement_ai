"""Tests for src/pdf_review.py: decoding, validating, and rendering uploaded
PDFs. Uses small PDFs generated in-memory with pypdfium2 rather than
committing real (or even fake) bank statement files -- no network access
and no financial data involved.
"""
import base64
import io

import pypdfium2 as pdfium
import pytest

from src import pdf_review


def _make_pdf_bytes(num_pages: int = 1) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(num_pages):
        pdf.new_page(200, 300)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def _data_uri(pdf_bytes: bytes) -> str:
    return "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode()


# --- decode_upload ---

def test_decode_upload_valid_data_uri():
    pdf_bytes = _make_pdf_bytes()
    decoded = pdf_review.decode_upload(_data_uri(pdf_bytes))
    assert decoded == pdf_bytes


def test_decode_upload_rejects_missing_comma():
    with pytest.raises(pdf_review.InvalidPDFError):
        pdf_review.decode_upload("not-a-data-uri")


def test_decode_upload_rejects_invalid_base64():
    with pytest.raises(pdf_review.InvalidPDFError):
        pdf_review.decode_upload("data:application/pdf;base64,not-valid-base64!!")


def test_decode_upload_rejects_empty_string():
    with pytest.raises(pdf_review.InvalidPDFError):
        pdf_review.decode_upload("")


# --- load_document ---

def test_load_document_returns_correct_page_count():
    pdf_bytes = _make_pdf_bytes(num_pages=3)
    doc = pdf_review.load_document("statement.pdf", pdf_bytes)
    assert doc.page_count == 3
    assert doc.filename == "statement.pdf"
    assert doc.pdf_bytes == pdf_bytes


def test_load_document_id_is_stable_for_same_bytes():
    pdf_bytes = _make_pdf_bytes()
    doc_a = pdf_review.load_document("a.pdf", pdf_bytes)
    doc_b = pdf_review.load_document("b.pdf", pdf_bytes)
    # Same content -> same id, even with different filenames.
    assert doc_a.document_id == doc_b.document_id


def test_load_document_id_differs_for_different_bytes():
    doc_a = pdf_review.load_document("a.pdf", _make_pdf_bytes(num_pages=1))
    doc_b = pdf_review.load_document("b.pdf", _make_pdf_bytes(num_pages=2))
    assert doc_a.document_id != doc_b.document_id


def test_load_document_rejects_corrupt_pdf():
    with pytest.raises(pdf_review.InvalidPDFError):
        pdf_review.load_document("bad.pdf", b"this is not a pdf")


def test_load_document_rejects_empty_bytes():
    with pytest.raises(pdf_review.InvalidPDFError):
        pdf_review.load_document("empty.pdf", b"")


# --- render_page_png_base64 ---

def test_render_page_returns_valid_png_base64():
    pdf_bytes = _make_pdf_bytes()
    result = pdf_review.render_page_png_base64(pdf_bytes, 1)
    png_bytes = base64.b64decode(result)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # PNG magic number


def test_render_page_out_of_range_raises():
    pdf_bytes = _make_pdf_bytes(num_pages=1)
    with pytest.raises(pdf_review.PageOutOfRangeError):
        pdf_review.render_page_png_base64(pdf_bytes, 2)


def test_render_page_rejects_page_zero():
    pdf_bytes = _make_pdf_bytes(num_pages=1)
    with pytest.raises(pdf_review.PageOutOfRangeError):
        pdf_review.render_page_png_base64(pdf_bytes, 0)


def test_render_different_pages_of_multi_page_pdf():
    pdf_bytes = _make_pdf_bytes(num_pages=2)
    page1 = pdf_review.render_page_png_base64(pdf_bytes, 1)
    page2 = pdf_review.render_page_png_base64(pdf_bytes, 2)
    # Both should render successfully and be valid (non-empty) PNGs.
    assert page1 and page2
    assert base64.b64decode(page1).startswith(b"\x89PNG")
    assert base64.b64decode(page2).startswith(b"\x89PNG")


# --- make_document_id ---

def test_make_document_id_is_deterministic():
    pdf_bytes = _make_pdf_bytes()
    assert pdf_review.make_document_id(pdf_bytes) == pdf_review.make_document_id(pdf_bytes)
