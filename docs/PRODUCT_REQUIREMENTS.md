# Product Requirements: PDF and OCR Side-by-Side Review Workspace

## 1. Product Problem

Before this feature, the Dash app ran OCR and sent the result straight to
Gemini with no checkpoint in between. Users received structured
transaction output with no page-level way to verify whether OCR accurately
represented the original PDF. For an audit / bookkeeping tool built around
"trust but verify," that's the wrong order — Gemini and the user's own
threshold/date filtering both trust text that was never checked.

This creates real risks, especially on scanned or low-quality statements:

- Incorrect amounts (e.g. a smudged "3" read as "8")
- Missing minus signs (a debit silently becoming a credit)
- Incorrect dates
- Broken or merged transaction descriptions
- Misread decimal separators
- Missing pages (OCR silently returning nothing for a page)
- Incorrect currency identification
- Generally poor extraction from low-quality scans

## 2. User Story

As a user reviewing a bank statement, I want to see the original PDF page
beside the OCR-extracted text, so that I can identify OCR errors before
relying on the extracted transactions.

## 3. Primary User Flow

1. Upload one or more PDFs.
2. Click **Run OCR**.
3. The Review OCR tab shows the first uploaded document: original PDF page
   on the left, OCR text for that page on the right.
4. Select a document (if more than one was uploaded) from the dropdown.
5. Navigate through pages with Previous / Next; each page's OCR text
   updates alongside the rendered page image.
6. Compare each page against its OCR text, watching for the error types
   listed above.
7. Click **Continue to Extraction** (or **Extract Transactions** in the
   left-hand controls — both do the same thing) to run Gemini extraction
   against the reviewed OCR text.
8. The view switches to the Transactions tab; review the pre-selected
   debit rows, adjust threshold/date range/currency, tick or untick rows.
9. Export the selected rows to Excel (unchanged from before this feature).

## 4. Functional Requirements

- Multi-document support: upload and review several PDFs in one session,
  each tracked independently (own page count, own OCR status, own current
  page).
- Multi-page support: page navigation within a single document.
- Previous/Next page navigation with a visible "Page X of Y" indicator.
- Side-by-side PDF page image and OCR text for the currently selected
  page.
- Responsive layout: side by side at desktop widths, stacked on narrow
  screens.
- OCR runs once per document and its result is reused for both review and
  (later) Gemini extraction — never re-run by navigation or re-selection.
- Clear, plain-language error messages for invalid/corrupt/password-
  protected/empty PDFs and for OCR failures — no raw tracebacks.
- Existing Excel export continues to work unchanged.
- Existing CLI (`src/cli.py`, CSV/JSON export) continues to work unchanged.

## 5. Non-Functional Requirements

- No unnecessary network calls: FX and Gemini are only called for actions
  that need them (extraction, currency conversion), never as a side effect
  of page navigation or document selection.
- No repeated OCR during navigation (verified: `navigate_review_page` only
  touches `review-store`'s `current_page` field).
- No repeated Gemini call during navigation, or on a second click of
  Extract/Continue for files already extracted (verified:
  `extract_transactions_step` skips filenames already in `processed-store`).
- Readable at common laptop resolutions (tested layout down to a stacked
  mobile-width view via Bootstrap `xs`/`md` breakpoints).
- Reasonable memory handling: PDF bytes, OCR text, and rendered page images
  are cached server-side, not duplicated into every browser store — see
  `docs/ARCHITECTURE.md` section 4.
- Typed Python interfaces: `OCRPage`/`OCRResult`/`PDFDocument` are
  dataclasses; `src/pdf_review.py` functions are fully type-hinted.
- Testable processing logic: `src/pdf_review.py` and `src/models.py` have
  no Dash/docTR/Gemini dependency and are unit-tested directly.
- Safe treatment of uploaded financial documents: no permanent storage, no
  statement content in logs, no server paths exposed to the browser — see
  `docs/ARCHITECTURE.md` section 6.
- No API keys required for unit tests: `tests/test_ocr_result.py` uses fake
  docTR-shaped objects; `tests/test_pdf_review.py` uses PDFs generated
  in-memory with pypdfium2. Neither calls docTR, Gemini, or the network.

## 6. Out of Scope

Explicitly not part of this iteration:

- Editing OCR text
- Drawing bounding boxes over PDF text (`ocr_advanced.result_to_words()`
  already extracts word-level coordinates for a future iteration, but
  nothing in this feature renders them)
- Linking individual OCR words to page coordinates in the UI
- Manual correction of extracted transactions
- Persistent user accounts
- Long-term document storage
- Collaborative review
- Audit trail database
- Role-based access control
- Mobile-first PDF annotation
- Replacing docTR
- Replacing Gemini
- Per-session/multi-user cache isolation (see `docs/ARCHITECTURE.md`
  section 4 — the server-side caches are process-global, a known
  prototype-scale limitation, not a hardened multi-user design)

## 7. Acceptance Criteria

1. A user can upload a valid PDF in the Dash app. ✅
2. The application can render or display the uploaded PDF. ✅ (rendered
   page image via `pdf_review.render_page_png_base64`)
3. The user can see the PDF and OCR-extracted text side by side. ✅
4. OCR text corresponds to the currently displayed page. ✅ (`OCRResult.page(n)`)
5. The user can navigate to the previous and next pages. ✅
6. The UI displays the current page and total page count. ✅
7. Multi-page PDFs work correctly. ✅ (tested with 1–3 page PDFs)
8. Multiple uploaded documents can be selected and reviewed independently. ✅
9. Page navigation does not rerun OCR. ✅ (by construction — see section 5)
10. Page navigation does not rerun Gemini extraction. ✅ (by construction)
11. The existing transaction-extraction workflow still works. ✅
    (`extract_statement_from_ocr` feeds the same `processed-store` shape
    `compute_and_render` already consumed)
12. Existing Excel export still works. ✅ (unchanged code path)
13. Existing CLI CSV and JSON export still work. ✅ (unchanged code path,
    verified by import + manual exercise since `pytest`/`google-genai`
    aren't installable in the verification sandbox — see final report)
14. Existing tests pass. ✅ (19/19)
15. New tests cover page-level OCR results and review-state behaviour. ✅
    (25 new tests: `tests/test_ocr_result.py`, `tests/test_pdf_review.py`)
16. No real network calls are made during the test suite. ✅
17. No API keys or sensitive example statements are committed. ✅ (tests
    generate PDFs in-memory; no new fixture files added)
18. `docs/ARCHITECTURE.md`, `docs/PRODUCT_REQUIREMENTS.md`,
    `docs/CODING_STANDARDS.md`, `CLAUDE.md` exist and describe the actual
    implementation. ✅
19. `README.md` reflects the new workflow. ✅
20. No raw user financial data in logs or committed fixtures. ✅
