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

Session-scoped as of this change: every entry is keyed by
`(session_id, document_id)`, not `document_id` alone. Before this, the
store was a single flat dict shared by every visitor to a deployment --
anyone hitting `GET /api/documents` saw every document anyone had ever
uploaded, and two people uploading the same file (same content hash, see
`src/pdf_review.make_document_id`) would silently overwrite each other's
state. `session_id` comes from an httpOnly cookie issued by
`backend/main.py`'s `get_session_id()` dependency, one per browser, so each
visitor now only ever sees and can only ever affect their own documents.
See docs/ARCHITECTURE.md for the full writeup.

Remaining prototype-scale caveat: this is still one process-global dict in
one process's memory -- fine for a single `uvicorn` worker (the systemd
deploy in deploy/backend.service runs exactly one), but it does not extend
to multiple worker processes or horizontally-scaled instances, which would
each hold their own separate store with no shared state between them. That
would need an external store (Redis, a database) -- out of scope for this
change, see docs/ARCHITECTURE.md.
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
    """Dict of DocumentState keyed by (session_id, document_id), behind a lock.

    uvicorn's default worker runs one asyncio event loop, and FastAPI runs
    blocking `def` route handlers (OCR, DeepSeek calls) in a thread pool --
    so more than one request genuinely can touch this store concurrently.
    The lock is intentionally coarse-grained: this store is small and
    every operation is fast (dict get/set), so a single lock is simpler and
    safe, not a bottleneck worth optimising away in a prototype.

    Every method takes `session_id` as its first argument -- callers (all
    in backend/main.py) get it from the `get_session_id` dependency, never
    from anything the client can directly claim to be (it's read from an
    httpOnly cookie the server itself issued), so one visitor cannot simply
    assert a different session_id to reach another visitor's documents.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._documents: dict[tuple[str, str], DocumentState] = {}

    def put(self, session_id: str, document: DocumentState) -> None:
        with self._lock:
            self._documents[(session_id, document.document_id)] = document

    def get(self, session_id: str, document_id: str) -> DocumentState | None:
        with self._lock:
            return self._documents.get((session_id, document_id))

    def all(self, session_id: str) -> list[DocumentState]:
        with self._lock:
            # Insertion order == upload order, which is what the frontend
            # wants for a stable document list. Only this session's own
            # documents -- see class docstring.
            return [doc for (sid, _), doc in self._documents.items() if sid == session_id]

    def delete(self, session_id: str, document_id: str) -> bool:
        with self._lock:
            return self._documents.pop((session_id, document_id), None) is not None

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
