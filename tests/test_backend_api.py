"""Tests for the FastAPI backend (backend/main.py, backend/store.py).

No real docTR/PyTorch inference, no real DeepSeek/network calls: OCR and
extraction are monkeypatched at their backend.main import site, the same
"mock the boundary" pattern tests/test_fx.py and tests/test_llm_extract.py
already use. PDFs are generated in-memory with pypdfium2, matching
tests/test_pdf_review.py, rather than committing sample files.
"""
from __future__ import annotations

import io

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.store import store
from src.models import OCRPage, OCRResult
from src.parse import Transaction
from decimal import Decimal


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _make_pdf_bytes(num_pages: int = 1) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(num_pages):
        pdf.new_page(200, 300)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def _upload(client: TestClient, filename: str = "statement.pdf", pages: int = 2):
    files = {"file": (filename, _make_pdf_bytes(pages), "application/pdf")}
    return client.post("/api/documents", files=files)


# --- upload / list / delete ---

def test_upload_valid_pdf_returns_summary(client):
    resp = _upload(client, pages=3)
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "statement.pdf"
    assert body["page_count"] == 3
    assert body["ocr_status"] == "pending"
    assert body["has_extraction"] is False
    assert body["document_id"]  # non-empty


def test_upload_invalid_pdf_returns_422(client):
    files = {"file": ("bad.pdf", b"not a pdf", "application/pdf")}
    resp = client.post("/api/documents", files=files)
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_list_documents_reflects_uploads(client):
    _upload(client, filename="a.pdf")
    _upload(client, filename="b.pdf")
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    filenames = {d["filename"] for d in resp.json()}
    assert filenames == {"a.pdf", "b.pdf"}


def test_delete_document_removes_it(client):
    doc_id = _upload(client).json()["document_id"]
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 204
    assert client.get("/api/documents").json() == []


def test_delete_unknown_document_returns_404(client):
    resp = client.delete("/api/documents/does-not-exist")
    assert resp.status_code == 404


# --- OCR ---

def test_run_ocr_success_is_cached_and_idempotent(client, monkeypatch):
    doc_id = _upload(client, pages=2).json()["document_id"]

    calls = {"count": 0}

    def _fake_run_ocr_only(pdf_path):
        calls["count"] += 1
        return OCRResult(pages=(OCRPage(1, "line one"), OCRPage(2, "line two")))

    monkeypatch.setattr("backend.main.run_ocr_only", _fake_run_ocr_only)

    resp1 = client.post(f"/api/documents/{doc_id}/ocr")
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["ocr_status"] == "done"
    assert [p["text"] for p in body1["pages"]] == ["line one", "line two"]

    resp2 = client.post(f"/api/documents/{doc_id}/ocr")
    assert resp2.status_code == 200
    assert calls["count"] == 1  # second call served from cache, OCR not re-run


def test_run_ocr_failure_is_recorded_not_raised(client, monkeypatch):
    doc_id = _upload(client).json()["document_id"]

    def _boom(pdf_path):
        raise RuntimeError("docTR not installed")

    monkeypatch.setattr("backend.main.run_ocr_only", _boom)

    resp = client.post(f"/api/documents/{doc_id}/ocr")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ocr_status"] == "error"
    assert "docTR not installed" in body["ocr_error"]


def test_run_ocr_unknown_document_404(client):
    resp = client.post("/api/documents/does-not-exist/ocr")
    assert resp.status_code == 404


# --- extraction ---

def _run_fake_ocr(client, monkeypatch, doc_id):
    monkeypatch.setattr(
        "backend.main.run_ocr_only",
        lambda pdf_path: OCRResult(pages=(OCRPage(1, "TESCO STORES -62.40"),)),
    )
    client.post(f"/api/documents/{doc_id}/ocr")


def test_extract_before_ocr_returns_409(client):
    doc_id = _upload(client).json()["document_id"]
    resp = client.post(f"/api/documents/{doc_id}/extract")
    assert resp.status_code == 409


def test_extract_success_is_cached_and_idempotent(client, monkeypatch):
    doc_id = _upload(client).json()["document_id"]
    _run_fake_ocr(client, monkeypatch, doc_id)

    calls = {"count": 0}

    def _fake_extract(ocr_result):
        calls["count"] += 1
        return "GBP", [Transaction(date="01 Nov 19", iso_date="2019-11-01", description="TESCO", amount=Decimal("-62.40"), raw_line="")]

    monkeypatch.setattr("backend.main.extract_statement_from_ocr", _fake_extract)

    resp1 = client.post(f"/api/documents/{doc_id}/extract")
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["source_currency"] == "GBP"
    assert len(body1["transactions"]) == 1

    resp2 = client.post(f"/api/documents/{doc_id}/extract")
    assert resp2.status_code == 200
    assert calls["count"] == 1  # second call served from cache, DeepSeek not re-called


def test_extract_failure_returns_502(client, monkeypatch):
    doc_id = _upload(client).json()["document_id"]
    _run_fake_ocr(client, monkeypatch, doc_id)

    def _boom(ocr_result):
        raise RuntimeError("DeepSeek API unreachable")

    monkeypatch.setattr("backend.main.extract_statement_from_ocr", _boom)

    resp = client.post(f"/api/documents/{doc_id}/extract")
    assert resp.status_code == 502


# --- compute / export ---

def _extracted_document(client, monkeypatch, transactions, currency="GBP"):
    doc_id = _upload(client).json()["document_id"]
    _run_fake_ocr(client, monkeypatch, doc_id)
    monkeypatch.setattr("backend.main.extract_statement_from_ocr", lambda ocr_result: (currency, transactions))
    client.post(f"/api/documents/{doc_id}/extract")
    return doc_id


def test_compute_filters_debits_and_applies_threshold(client, monkeypatch):
    transactions = [
        Transaction(date="01 Nov 19", iso_date="2019-11-01", description="Big payment", amount=Decimal("-500.00"), raw_line=""),
        Transaction(date="02 Nov 19", iso_date="2019-11-02", description="Small payment", amount=Decimal("-10.00"), raw_line=""),
        Transaction(date="03 Nov 19", iso_date="2019-11-03", description="Salary", amount=Decimal("1500.00"), raw_line=""),
    ]
    _extracted_document(client, monkeypatch, transactions)

    resp = client.post(
        "/api/transactions/compute",
        json={"threshold": 100, "target_currency": "AUTO", "start_date": None, "end_date": None},
    )
    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert len(docs) == 1
    rows = docs[0]["rows"]
    # Only debits appear (credit "Salary" excluded); both debits shown, only the
    # large one pre-selected because it's the only one at/above the threshold.
    assert [r["description"] for r in rows] == ["Big payment", "Small payment"]
    assert docs[0]["selected_indices"] == [0]
    assert docs[0]["display_currency"] == "GBP"  # AUTO -> source currency


def test_compute_respects_date_range(client, monkeypatch):
    transactions = [
        Transaction(date="01 Nov 19", iso_date="2019-11-01", description="Early", amount=Decimal("-50.00"), raw_line=""),
        Transaction(date="15 Dec 19", iso_date="2019-12-15", description="Late", amount=Decimal("-50.00"), raw_line=""),
    ]
    _extracted_document(client, monkeypatch, transactions)

    resp = client.post(
        "/api/transactions/compute",
        json={"threshold": 0, "target_currency": "AUTO", "start_date": "2019-12-01", "end_date": "2019-12-31"},
    )
    rows = resp.json()["documents"][0]["rows"]
    assert [r["description"] for r in rows] == ["Late"]


def test_compute_ignores_documents_without_extraction(client):
    _upload(client)  # never OCR'd or extracted
    resp = client.post(
        "/api/transactions/compute",
        json={"threshold": 0, "target_currency": "AUTO", "start_date": None, "end_date": None},
    )
    assert resp.json()["documents"] == []


def test_export_excel_returns_xlsx_for_selected_rows(client, monkeypatch):
    transactions = [
        Transaction(date="01 Nov 19", iso_date="2019-11-01", description="Keep me", amount=Decimal("-500.00"), raw_line=""),
        Transaction(date="02 Nov 19", iso_date="2019-11-02", description="Drop me", amount=Decimal("-5.00"), raw_line=""),
    ]
    doc_id = _extracted_document(client, monkeypatch, transactions)
    client.post(
        "/api/transactions/compute",
        json={"threshold": 0, "target_currency": "AUTO", "start_date": None, "end_date": None},
    )

    resp = client.post("/api/export/excel", json={"selections": {doc_id: [0]}})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")

    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Date", "Description", "Amount (GBP)")
    assert rows[1] == ("01 Nov 19", "Keep me", "-500.00")
    assert len(rows) == 2  # header + the one selected row, "Drop me" excluded
