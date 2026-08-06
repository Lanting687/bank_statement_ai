"""Pydantic request/response models for the FastAPI backend.

Kept separate from backend/store.py's dataclasses deliberately: the store
holds internal state (including raw PDF bytes, which must never be
serialized back to the client -- see docs/ARCHITECTURE.md's security
section), while these models define exactly what crosses the wire.
"""
from __future__ import annotations

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    page_count: int
    ocr_status: str  # "pending" | "done" | "error"
    ocr_error: str | None = None
    has_extraction: bool


class OCRPageOut(BaseModel):
    page_number: int
    text: str


class OCRResultOut(BaseModel):
    document_id: str
    ocr_status: str
    ocr_error: str | None = None
    page_count: int
    pages: list[OCRPageOut]


class TransactionOut(BaseModel):
    date: str
    iso_date: str
    description: str
    amount: str


class ExtractionOut(BaseModel):
    document_id: str
    source_currency: str
    transactions: list[TransactionOut]


class ComputeRequest(BaseModel):
    threshold: float = 0
    target_currency: str = "AUTO"
    start_date: str | None = None
    end_date: str | None = None


class ComputedRowOut(BaseModel):
    date: str
    iso_date: str
    description: str
    converted_amount: str


class ComputedDocumentOut(BaseModel):
    document_id: str
    filename: str
    display_currency: str
    rows: list[ComputedRowOut]
    selected_indices: list[int]
    warning: str | None = None


class ComputeResponse(BaseModel):
    documents: list[ComputedDocumentOut]


class ExportRequest(BaseModel):
    # document_id -> row indices the user has ticked, taken from the most
    # recent /api/transactions/compute response for that document.
    selections: dict[str, list[int]]
