"""
In-memory, process-lifetime store for uploaded documents and their derived
state (OCR result, DeepSeek extraction, last computed transaction rows).

This is the server-side replacement for what the Dash version of this app
spread across two places: small Dash `dcc.Store` data held by the browser,
and the module-level `_PDF_CACHE` / `_OCR_CACHE` / `_PAGE_IMAGE_CACHE`
dicts in `app.py` (see the Dash-era `docs/ARCHITECTURE.md` history). With a
Next.js frontend there is no equivalent of `dcc.Store` -- the frontend is
stateless between requests -- so *all* per-document state now lives here,
addressed by `document_id`, and the frontend just asks for what it needs.

Same prototype-scale caveat as the Dash version: this is one process-global
dict, not session-scoped. Fine for one local user running `uvicorn` and
`next dev` on their own machine; not safe for concurrent multi-user
deployment without further work (per-session keys, eviction, a real cache)
-- see docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from src.models import OCRResult
from src.parse import Transaction


@dataclass
class ExtractionState:
    source_currency: str
    transactions: list[Transaction]


@dataclass
class ComputedRow:
    date: str
    iso_date: str
    description: str
    converted_amount: str


@dataclass
class ComputedState:
    display_currency: str
    rows: list[ComputedRow]
    selected_indices: list[int]
    warning: str | None


@dataclass
class DocumentState:
    document_id: str
    filename: str
    pdf_bytes: bytes
    page_count: int
    ocr_status: str = "pending"  # "pending" | "done" | "error"
    ocr_error: str | None = None
    ocr_result: OCRResult | None = None
    extraction: ExtractionState | None = None
    computed: ComputedState | None = None


class DocumentStore:
    """Dict of DocumentState keyed by document_id, behind a lock.

    uvicorn's default worker runs one asyncio event loop, and FastAPI runs
    blocking `def` route handlers (OCR, DeepSeek calls) in a thread pool --
    so more than one request genuinely can touch this store concurrently.
    The lock is intentionally coarse-grained: this store is small and
    every operation is fast (dict get/set), so a single lock is simpler and
    safe, not a bottleneck worth optimising away in a prototype.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._documents: dict[str, DocumentState] = {}

    def put(self, document: DocumentState) -> None:
        with self._lock:
            self._documents[document.document_id] = document

    def get(self, document_id: str) -> DocumentState | None:
        with self._lock:
            return self._documents.get(document_id)

    def all(self) -> list[DocumentState]:
        with self._lock:
            # Insertion order == upload order, which is what the frontend
            # wants for a stable document list.
            return list(self._documents.values())

    def delete(self, document_id: str) -> bool:
        with self._lock:
            return self._documents.pop(document_id, None) is not None

    def clear(self) -> None:
        """Empty the store. Not used by any route -- exists for tests, so
        each test starts from a clean slate despite `store` being a
        process-lifetime singleton (see tests/test_backend_api.py)."""
        with self._lock:
            self._documents.clear()


# Single process-lifetime instance, imported by main.py. Deliberately a
# plain module-level singleton rather than dependency-injected per request
# -- there is exactly one of these for the life of the server process.
store = DocumentStore()
