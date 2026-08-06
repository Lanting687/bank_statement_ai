# Product Requirements

Covers both the original OCR side-by-side review feature and the
subsequent Next.js + FastAPI rearchitecture (replacing the Dash UI) that
delivers the same requirements through a different stack.

## 1. Product Problem

Before the OCR review feature, this app ran OCR and sent the result
straight to the LLM (DeepSeek) with no checkpoint in between. Users
received structured transaction output with no page-level way to verify
whether OCR accurately represented the original PDF. For an audit /
bookkeeping tool built around "trust but verify," that's the wrong order —
DeepSeek and the user's own threshold/date filtering both trust text that
was never checked.

This creates real risks, especially on scanned or low-quality statements:

- Incorrect amounts (e.g. a smudged "3" read as "8")
- Missing minus signs (a debit silently becoming a credit)
- Incorrect dates
- Broken or merged transaction descriptions
- Misread decimal separators
- Missing pages (OCR silently returning nothing for a page)
- Incorrect currency identification
- Generally poor extraction from low-quality scans

Separately, the original Dash UI — while functional — looked and felt like
a prototype: default Bootstrap styling, no polish, limited layout
flexibility. For a tool meant to save a professional (auditor,
bookkeeper) real review time, the interface itself needed to look and
behave like a tool they'd trust and want to keep using, not a demo.

## 2. User Story

As a user reviewing a bank statement, I want to see the original PDF page
beside the OCR-extracted text, in a fast, clean interface, so that I can
identify OCR errors before relying on the extracted transactions.

## 3. Primary User Flow

1. Upload one or more PDFs (drag-and-drop or click to browse).
2. OCR starts automatically per file (it's local/free — no API cost, no
   reason to make the user click twice per file).
3. In the **Review OCR** tab, pick a document from the sidebar list (if
   more than one was uploaded); the original PDF page and its OCR text
   appear side by side.
4. Use **Previous** / **Next** to page through the document, comparing
   each page against its OCR text, watching for the error types listed
   above.
5. Click **Continue to Extraction** (in the review panel) or **Extract
   Transactions** (in the sidebar, which processes every OCR'd document at
   once) — either runs DeepSeek extraction and switches to the
   **Transactions** tab.
6. Set a **minimum payment amount**, optional **date range**, and
   **display currency** in the sidebar; the transaction table updates
   automatically.
7. Review the pre-selected debit rows; tick or untick as needed.
8. Click **Download Excel** to export the selected rows.

## 4. Functional Requirements

- Multi-document support: upload and review several PDFs in one session,
  each tracked independently (own page count, own OCR status, own current
  review page, own extraction status).
- Multi-page support: page navigation within a single document, rendered
  client-side (`pdf.js`) at the panel's actual size.
- Previous/Next page navigation with a visible "Page X of Y" indicator.
- Side-by-side PDF page image and OCR text for the currently selected
  page, responsive down to a single stacked column on narrow screens.
- OCR runs once per document (automatically, on upload) and its result is
  cached server-side and reused for both review and extraction — never
  re-run by navigation, re-selection, or revisiting a document.
- DeepSeek extraction is explicit (never automatic) and idempotent per
  document — re-triggering it for an already-extracted document does not
  call DeepSeek again.
- Clear, plain-language error messages for invalid/corrupt/password-
  protected/empty PDFs, OCR failures, and DeepSeek failures — no raw
  tracebacks or stack traces anywhere in the UI.
- A document can be removed from the session entirely (upload mistakes,
  wrong file) — new in this iteration; the Dash version had no equivalent.
- Existing Excel export continues to work: selected rows only, one sheet
  per document, same column layout.
- Existing CLI (`src/cli.py`, CSV/JSON export) continues to work unchanged
  — it does not talk to the backend API at all, it still calls `src/`
  directly.

## 5. Non-Functional Requirements

- No unnecessary network calls: FX and DeepSeek are only called for
  actions that need them, never as a side effect of page navigation,
  document selection, or a browser reload.
- No repeated OCR during navigation or on revisiting a document (verified:
  page navigation is pure client-side state; `POST /api/documents/{id}/ocr`
  is idempotent).
- No repeated DeepSeek call on a second "Extract" click for an
  already-extracted document (verified: `POST /api/documents/{id}/extract`
  is idempotent; the frontend also pre-filters which documents it offers to
  extract).
- **Professional, responsive UI**: built with Tailwind CSS and a
  hand-authored shadcn/ui-style component kit (`frontend/components/ui/`)
  — consistent spacing, typography, color tokens, accessible focus states,
  and a layout that adapts from desktop (side-by-side review panels, fixed
  sidebar) down to mobile (stacked panels, full-width sidebar).
- Readable at common laptop resolutions and usable on a tablet/phone
  viewport.
- Reasonable memory handling: PDF bytes, OCR text, and extracted
  transactions are cached server-side in `backend/store.py`, not duplicated
  into browser storage; only small per-document metadata (status, page
  count, current page) lives in frontend state.
- Typed interfaces on both sides: `OCRPage`/`OCRResult`/`PDFDocument`
  (Python dataclasses) and Pydantic schemas in `backend/schemas.py` on the
  backend; TypeScript interfaces in `frontend/lib/types.ts` on the
  frontend.
- Testable processing logic: `src/pdf_review.py`, `src/models.py`, and
  `backend/main.py`'s routes are all unit-tested with mocked external
  services, no live server required.
- Safe treatment of uploaded financial documents: no permanent storage, no
  statement content in logs, no server paths exposed to the browser, PDF
  bytes never sent back to the browser by the API — see
  `docs/ARCHITECTURE.md` section 6.
- No API keys required for unit tests: OCR is mocked with fake docTR-shaped
  objects, DeepSeek/FX are monkeypatched at their call site, matching the
  pattern already established in `tests/test_fx.py` and
  `tests/test_llm_extract.py`.

## 6. Out of Scope

Explicitly not part of this iteration:

- Editing OCR text
- Drawing bounding boxes over PDF text (`ocr_advanced.result_to_words()`
  already extracts word-level coordinates for a future iteration, but
  nothing in this feature renders them)
- Linking individual OCR words to page coordinates in the UI
- Manual correction of extracted transactions
- Persistent user accounts or authentication
- Long-term document storage / a database
- Collaborative review
- Audit trail database
- Role-based access control
- Server-rendered PDF preview images (deliberately replaced with
  client-side `pdf.js` rendering — see `docs/ARCHITECTURE.md` section 4 for
  the trade-off; `src/pdf_review.render_page_png_base64()` still exists and
  is tested, but nothing in the running app calls it anymore)
- Real shadcn/ui + Radix UI component installation (the current kit is a
  hand-authored, visually-equivalent stand-in — see
  `docs/CODING_STANDARDS.md`)
- Generated TypeScript types from the OpenAPI schema (types are hand-kept
  in sync — see `docs/ARCHITECTURE.md` section 3)
- Replacing docTR
- Replacing the LLM extraction provider (already DeepSeek, not Gemini —
  out of scope to change again in this iteration)
- Per-session/multi-user cache isolation (the server-side `DocumentStore`
  is process-global, a known prototype-scale limitation, not a hardened
  multi-user design — see `docs/ARCHITECTURE.md` section 4)

## 7. Acceptance Criteria

1. A user can upload a valid PDF via the Next.js app. ✅
2. The application renders the uploaded PDF in the browser (client-side,
   `pdf.js`). ✅
3. The user can see the PDF and OCR-extracted text side by side. ✅
4. OCR text corresponds to the currently displayed page. ✅
5. The user can navigate to the previous and next pages. ✅
6. The UI displays the current page and total page count. ✅
7. Multi-page PDFs work correctly. ✅
8. Multiple uploaded documents can be selected and reviewed independently,
   each retaining its own current page. ✅
9. Page navigation does not rerun OCR. ✅ (client-side state only)
10. Page navigation does not rerun DeepSeek extraction. ✅
11. A document can be removed from the session. ✅ (new: `DELETE
    /api/documents/{id}`)
12. The transaction-extraction workflow works end-to-end: OCR → review →
    extract → filter → select → export. ✅
13. Excel export produces the same shape as before (one sheet per
    document, ticked rows only). ✅
14. The CLI (`src/cli.py`) still works unchanged, independent of the
    backend/frontend. ✅
15. Existing `src/` unit tests pass unmodified (19 pre-existing +
    `tests/test_llm_extract.py` added in the DeepSeek migration). ✅
16. New tests cover the FastAPI backend's routes (upload validation, OCR
    idempotency, extraction idempotency and error codes, compute filtering,
    Excel export) with no real docTR/DeepSeek/network calls. ✅
    (`tests/test_backend_api.py`)
17. No real network calls are made during the test suite. ✅
18. No API keys or sensitive example statements are committed. ✅
19. `docs/ARCHITECTURE.md`, `docs/PRODUCT_REQUIREMENTS.md`,
    `docs/CODING_STANDARDS.md`, `CLAUDE.md` describe the actual
    implementation, including the new split architecture. ✅
20. `README.md` reflects the new two-process (`uvicorn` + `next dev`) local
    dev workflow. ✅
21. The UI is visibly more polished than the retired Dash version:
    consistent design system, responsive layout, accessible components. ✅
    (Tailwind + shadcn/ui-style kit — see `docs/CODING_STANDARDS.md`)
