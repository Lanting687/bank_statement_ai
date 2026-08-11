"""
FastAPI backend for Bank Statement AI.

Replaces the Dash app (`app.py`, now removed) as the server side of this
application. The Next.js frontend (`frontend/`) talks to this over HTTP;
this module owns no UI at all -- it wraps the same `src/` pipeline the
Dash app and the CLI (`src/cli.py`, unchanged) both use, and exposes it as
a small set of REST endpoints backed by `backend/store.py`.

Run with (from the repo root, same place you'd run `pytest`):
    uvicorn backend.main:app --reload --port 8000

See docs/ARCHITECTURE.md for the full request flow and why each piece of
state lives where it does.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src import pdf_review
from src.filter import in_date_range
from src.fx import convert
from src.pipeline import extract_statement_from_ocr, run_ocr_only

from .schemas import (
    ComputedDocumentOut,
    ComputedRowOut,
    ComputeRequest,
    ComputeResponse,
    DocumentSummary,
    ExportRequest,
    ExtractionOut,
    OCRPageOut,
    OCRResultOut,
    TransactionOut,
)
from .store import ComputedRow, ComputedState, DocumentState, ExtractionState, store

load_dotenv()

app = FastAPI(title="Bank Statement AI API", version="1.0.0")

# The Next.js dev server (localhost:3000) proxies /api/* to this server via
# next.config.js rewrites, so requests arrive same-origin from the
# browser's point of view and CORS normally never applies. This is kept as
# a defensive fallback for anyone calling the API directly (curl, the
# FastAPI /docs page, or a frontend dev server on a different port).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Needed for the session cookie (see get_session_id below) to survive
    # the cross-origin fallback case this middleware exists for -- without
    # allow_credentials, browsers drop Set-Cookie/Cookie on cross-origin
    # requests even with a matching allow_origins entry. The normal
    # same-origin path (browser -> Next.js -> rewrite -> here) doesn't need
    # this at all; it's for the "calling the API directly" cases in the
    # comment above.
    allow_credentials=True,
)

SESSION_COOKIE_NAME = "bsai_session"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def get_session_id(request: Request, response: Response) -> str:
    """Identify which browser is calling, so DocumentStore can keep each
    visitor's documents separate from everyone else's.

    Without this, every route below shared one flat process-global dict
    keyed only by document_id: any visitor's GET /api/documents returned
    every document anyone had ever uploaded, and any visitor could
    OCR/extract/delete/export any other visitor's document just by knowing
    (or being handed, via that same list response) its id. See
    docs/ARCHITECTURE.md for the full writeup of why that was unsafe for a
    deployment more than one person can reach.

    Issues a random session id as an httpOnly cookie the first time a
    browser hits any route that depends on this (httpOnly so client-side
    JS can't read or forge it; samesite=lax so it's still sent on normal
    top-level navigation). Every route that touches the store takes this
    as a dependency and passes it straight to DocumentStore, which is the
    only thing that actually enforces the isolation -- this function just
    identifies the caller.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        session_id = uuid.uuid4().hex
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return session_id


def _to_summary(doc: DocumentState) -> DocumentSummary:
    return DocumentSummary(
        document_id=doc.document_id,
        filename=doc.filename,
        page_count=doc.page_count,
        ocr_status=doc.ocr_status,
        ocr_error=doc.ocr_error,
        has_extraction=doc.extraction is not None,
    )


def _get_or_404(session_id: str, document_id: str) -> DocumentState:
    doc = store.get(session_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document with id {document_id!r}")
    return doc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/documents", response_model=DocumentSummary)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Depends(get_session_id),
) -> DocumentSummary:
    """Decode and validate an uploaded PDF; store it (OCR not run yet).

    Mirrors the Dash app's stage_uploads() + the validation load_document()
    already did inside run_ocr_step() -- split out here into its own step
    so the frontend gets fast per-file validation feedback (a corrupt PDF
    fails immediately) without waiting for OCR.
    """
    raw = await file.read()
    try:
        pdf_doc = pdf_review.load_document(file.filename or "upload.pdf", raw)
    except pdf_review.PDFReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc = DocumentState(
        document_id=pdf_doc.document_id,
        filename=pdf_doc.filename,
        pdf_bytes=pdf_doc.pdf_bytes,
        page_count=pdf_doc.page_count,
        ocr_status="pending",
    )
    store.put(session_id, doc)
    return _to_summary(doc)


@app.get("/api/documents", response_model=list[DocumentSummary])
def list_documents(session_id: str = Depends(get_session_id)) -> list[DocumentSummary]:
    return [_to_summary(doc) for doc in store.all(session_id)]


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str, session_id: str = Depends(get_session_id)) -> None:
    if not store.delete(session_id, document_id):
        raise HTTPException(status_code=404, detail=f"No document with id {document_id!r}")


# Note: this is a plain `def`, not `async def`. FastAPI runs sync route
# handlers in a worker thread pool instead of on the event loop -- OCR
# (docTR/PyTorch) is blocking, CPU-bound work, so this keeps one slow OCR
# call from freezing every other request the server is handling.
@app.post("/api/documents/{document_id}/ocr", response_model=OCRResultOut)
def run_ocr(
    document_id: str,
    force: bool = False,
    session_id: str = Depends(get_session_id),
) -> OCRResultOut:
    """Run OCR once per document and cache the page-level result.

    Idempotent by default (force=False): if OCR already ran, returns the
    cached OCRResult instead of re-running docTR -- this is what makes it
    safe for the frontend to call this again after the user revisits a
    document, without silently burning GPU/CPU time or changing state.
    """
    doc = _get_or_404(session_id, document_id)

    if doc.ocr_status == "done" and doc.ocr_result is not None and not force:
        return OCRResultOut(
            document_id=doc.document_id,
            ocr_status=doc.ocr_status,
            ocr_error=doc.ocr_error,
            page_count=doc.page_count,
            pages=[OCRPageOut(page_number=p.page_number, text=p.text) for p in doc.ocr_result.pages],
        )

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(doc.pdf_bytes)
            tmp.flush()
            ocr_result = run_ocr_only(tmp.name)
    except Exception as exc:
        # docTR/PyTorch can raise many different exception types we can't
        # enumerate; recorded on the document, not swallowed, not fatal to
        # any other document in the store.
        doc.ocr_status = "error"
        doc.ocr_error = str(exc)
        store.put(session_id, doc)
        return OCRResultOut(
            document_id=doc.document_id, ocr_status="error", ocr_error=doc.ocr_error,
            page_count=doc.page_count, pages=[],
        )

    doc.ocr_result = ocr_result
    doc.ocr_status = "done"
    doc.ocr_error = None
    store.put(session_id, doc)

    return OCRResultOut(
        document_id=doc.document_id,
        ocr_status="done",
        ocr_error=None,
        page_count=doc.page_count,
        pages=[OCRPageOut(page_number=p.page_number, text=p.text) for p in ocr_result.pages],
    )


@app.post("/api/documents/{document_id}/extract", response_model=ExtractionOut)
def extract_transactions(
    document_id: str,
    force: bool = False,
    session_id: str = Depends(get_session_id),
) -> ExtractionOut:
    """Run DeepSeek extraction against the cached OCRResult.

    Idempotent by default, same reasoning as run_ocr(): re-calling this
    for a document that's already been extracted returns the cached result
    instead of calling DeepSeek again.
    """
    doc = _get_or_404(session_id, document_id)

    if doc.ocr_status != "done" or doc.ocr_result is None:
        raise HTTPException(
            status_code=409,
            detail="Run OCR on this document before extracting transactions.",
        )

    if doc.extraction is not None and not force:
        return ExtractionOut(
            document_id=doc.document_id,
            source_currency=doc.extraction.source_currency,
            transactions=[
                TransactionOut(date=t.date, iso_date=t.iso_date, description=t.description, amount=str(t.amount))
                for t in doc.extraction.transactions
            ],
        )

    try:
        source_currency, transactions = extract_statement_from_ocr(doc.ocr_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"DeepSeek extraction failed: {exc}") from exc

    doc.extraction = ExtractionState(source_currency=source_currency, transactions=transactions)
    store.put(session_id, doc)

    return ExtractionOut(
        document_id=doc.document_id,
        source_currency=source_currency,
        transactions=[
            TransactionOut(date=t.date, iso_date=t.iso_date, description=t.description, amount=str(t.amount))
            for t in transactions
        ],
    )


@app.post("/api/transactions/compute", response_model=ComputeResponse)
def compute_transactions(
    body: ComputeRequest,
    session_id: str = Depends(get_session_id),
) -> ComputeResponse:
    """Filter + convert every extracted document's transactions.

    Same logic as the Dash app's compute_and_render(): debits only, FX
    conversion to the requested display currency, date-range filtering,
    and pre-selection of rows at/above the threshold. Runs across every
    document *in this caller's session* that has an extraction -- store.all()
    is already scoped to session_id, so this can never read or overwrite
    another visitor's documents. The frontend calls this once whenever
    threshold/currency/date range changes, not per document. Results are
    cached per document (in `computed`) so /api/export/excel doesn't need
    the frontend to resend row data, only which indices are ticked.
    """
    threshold_f = float(body.threshold)
    documents_out: list[ComputedDocumentOut] = []

    for doc in store.all(session_id):
        if doc.extraction is None:
            continue

        source_currency = doc.extraction.source_currency
        display_currency = source_currency if body.target_currency == "AUTO" else body.target_currency

        all_rows: list[ComputedRow] = []
        warning: str | None = None

        for t in doc.extraction.transactions:
            if t.amount >= 0:
                continue  # show paid-out (debit) transactions only
            converted_amount, fx_warning = convert(t.amount, source_currency, display_currency)
            warning = warning or fx_warning
            all_rows.append(ComputedRow(
                date=t.date, iso_date=t.iso_date, description=t.description,
                converted_amount=str(converted_amount),
            ))

        rows = [r for r in all_rows if in_date_range(r.iso_date, body.start_date, body.end_date)]
        selected = [i for i, r in enumerate(rows) if abs(float(r.converted_amount)) >= threshold_f]

        doc.computed = ComputedState(
            display_currency=display_currency, rows=rows, selected_indices=selected, warning=warning,
        )
        store.put(session_id, doc)

        documents_out.append(ComputedDocumentOut(
            document_id=doc.document_id,
            filename=doc.filename,
            display_currency=display_currency,
            rows=[ComputedRowOut(date=r.date, iso_date=r.iso_date, description=r.description, converted_amount=r.converted_amount) for r in rows],
            selected_indices=selected,
            warning=warning,
        ))

    return ComputeResponse(documents=documents_out)


def _sheet_name(filename: str) -> str:
    name = re.sub(r"[\\/*?:\[\]]", "_", filename.rsplit(".", 1)[0])
    return name[:31] or "sheet"


@app.post("/api/export/excel")
def export_excel(
    body: ExportRequest,
    session_id: str = Depends(get_session_id),
) -> StreamingResponse:
    """Build the selected rows into an .xlsx, one sheet per document.

    Uses each document's last /api/transactions/compute result (cached in
    `doc.computed`) plus the row indices the frontend says are ticked --
    same shape and behaviour as the Dash app's download_excel(). Looks up
    each document_id scoped to the caller's session, so a client can't
    export another visitor's document by guessing/supplying its id --
    store.get() simply returns None for an id that isn't in this session,
    identical to it never having existed.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for document_id, indices in body.selections.items():
            doc = store.get(session_id, document_id)
            if doc is None or doc.computed is None:
                continue
            selected = set(indices)
            rows = [
                {"date": r.date, "description": r.description, "converted_amount": r.converted_amount}
                for i, r in enumerate(doc.computed.rows) if i in selected
            ]
            df = pd.DataFrame(rows, columns=["date", "description", "converted_amount"])
            df.columns = ["Date", "Description", f"Amount ({doc.computed.display_currency})"]
            df.to_excel(writer, sheet_name=_sheet_name(doc.filename), index=False)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=transactions.xlsx"},
    )
