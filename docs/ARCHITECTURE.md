# Architecture

This document describes the actual implementation of Bank Statement AI as of
the "PDF and OCR Side-by-Side Review Workspace" feature. It is meant to be
read before making further architectural changes — see `CLAUDE.md`.

## 1. System Overview

Bank Statement AI has three entry points sharing one processing pipeline:

- **Dash web app** (`app.py`) — the primary interface. Upload one or more
  PDFs, run OCR, review the OCR output against the original page, extract
  transactions with DeepSeek, filter/select them, and export to Excel.
- **CLI** (`src/cli.py`) — a single-file, non-interactive path: PDF in,
  filtered CSV/JSON out. Used for scripting; has no review step.
- **Shared pipeline** (`src/`) — OCR, LLM extraction, filtering, FX
  conversion, and export logic, used by both of the above.

### Data flow

```mermaid
flowchart LR
    A[PDF Upload] --> B[Decode + Validate<br/>src/pdf_review.py]
    B --> C[docTR OCR<br/>src/ocr_advanced.py]
    C --> D[OCRResult: page 1..N<br/>src/models.py]
    D --> E[Review Workspace<br/>PDF page image + OCR text, side by side]
    E -->|user clicks Extract Transactions| F[DeepSeek Extraction<br/>src/llm_extract.py]
    F --> G[Pydantic Validation<br/>ExtractionResult]
    G --> H[Transaction dataclass<br/>src/parse.py]
    H --> I[Debit + Threshold + Date Filtering<br/>src/filter.py]
    I --> J[FX Conversion<br/>src/fx.py]
    J --> K[Human Transaction Review<br/>tick/untick rows]
    K --> L[Excel / CSV / JSON Export<br/>app.py download / src/export.py]
```

### Human review points

There are now two human-in-the-loop checkpoints, not one:

1. **OCR review** (new): after OCR runs, the user compares each PDF page
   against the text docTR extracted from it, before that text is ever sent
   to DeepSeek. This is the feature this document describes.
2. **Transaction review** (existing): after DeepSeek extraction, the user
   ticks/unticks pre-selected rows before exporting.

Splitting these two checkpoints means DeepSeek is only ever called once the
user has (optionally) sanity-checked the OCR text it will read — see
section 4 ("Primary Objective") in the original feature brief.

## 2. Module Responsibilities

| Module | Responsibility |
|---|---|
| `app.py` | Dash layout and callbacks. Owns UI-only, process-lifetime caches (`_PDF_CACHE`, `_OCR_CACHE`, `_PAGE_IMAGE_CACHE`). Callbacks are kept thin: they call into `src/` for all real logic and only assemble Dash outputs. |
| `src/cli.py` | Non-interactive entry point. Unchanged by this feature: still calls `pipeline.extract_transactions()` and writes CSV/JSON via `src/export.py`. No OCR review step. |
| `src/pdf_review.py` | **New.** Decodes an uploaded PDF (`decode_upload`), validates it and computes page count / a stable content-hash id (`load_document`), and renders a single page to a PNG for the browser (`render_page_png_base64`). Everything operates on in-memory bytes; nothing is written to disk. Raises typed errors (`InvalidPDFError`, `PasswordProtectedPDFError`, `PageOutOfRangeError`) instead of leaking pypdfium2 exceptions or raw tracebacks to the UI. |
| `src/models.py` | **New.** `OCRPage` / `OCRResult` — the page-aware OCR data model shared by `ocr_advanced.py`, `pipeline.py`, and `app.py`. |
| `src/ocr_advanced.py` | Runs docTR OCR (`run_ocr`, unchanged) and flattens the result. `result_to_ocr_result()` (new) builds an `OCRResult` with one `OCRPage` per PDF page. `result_to_text()` (existing signature, now implemented on top of `result_to_ocr_result`) and `extract_ocr()` (new convenience wrapper) sit alongside it — see section 3 for why both exist. docTR/PyTorch imports stay function-local inside `run_ocr()`, so importing this module (or `app.py`) never loads either library — they only load when OCR actually runs. |
| `src/llm_extract.py` | Sends OCR text to DeepSeek (`deepseek-v4-flash`) via a plain HTTP POST (`requests`), asking for JSON-mode output matching a shape spelled out in the system prompt, and validates the reply with a Pydantic model (`ExtractionResult.model_validate()`), returns `(currency, list[Transaction])`. Originally used Google Gemini via the `google-genai` SDK; switched to DeepSeek in a later change — the public function signature and return type are unchanged. |
| `src/pipeline.py` | Composes the above. Now exposes OCR and DeepSeek as separable steps (`run_ocr_only`, `extract_statement_from_ocr`) as well as the original combined call (`extract_statement`, `extract_transactions`) that the CLI still uses unmodified. |
| `src/parse.py` | `Transaction` dataclass. Unchanged. |
| `src/filter.py` | Debit/threshold and date-range filtering. Unchanged. |
| `src/fx.py` | Frankfurter FX lookup with an lru_cache and a 1:1 fallback on failure. Unchanged. |
| `src/export.py` | CLI's CSV/JSON writers. Unchanged; the Dash app's Excel export is built inline in `app.py` (`download_excel`), also unchanged. |

## 3. Data Models

### `Transaction` (`src/parse.py`, unchanged)

One line item: `date`, `description`, `amount` (signed `Decimal`), `raw_line`,
`iso_date`, and an `is_debit` property. This is the model DeepSeek extraction,
filtering, FX conversion, and export all share.

### `OCRPage` / `OCRResult` (`src/models.py`, new)

```python
@dataclass(frozen=True)
class OCRPage:
    page_number: int   # 1-indexed, matches the review UI's "Page X of Y"
    text: str          # recognised lines for this page, "" if none

@dataclass(frozen=True)
class OCRResult:
    pages: tuple[OCRPage, ...]

    @property
    def full_text(self) -> str: ...   # pages joined for DeepSeek / the CLI

    @property
    def page_count(self) -> int: ...

    def page(self, page_number: int) -> OCRPage | None: ...
```

**Why both a page-level model and a full-text property, instead of just
changing `result_to_text()`'s return type:** the CLI and `llm_extract.py`
only ever want one combined string; the review workspace only ever wants
"the text for page N." Rather than pick one shape and force the other
caller to adapt, `OCRResult.full_text` derives the flattened string from
the same page list the UI renders from, so both views are guaranteed to
agree and OCR only has to run once. `full_text` skips pages with no
recognised text so it reproduces byte-for-byte what the old
`result_to_text()` returned before this refactor (see
`tests/test_ocr_result.py::test_result_to_text_matches_full_text_for_same_document`).

### `PDFDocument` (`src/pdf_review.py`, new)

```python
@dataclass(frozen=True)
class PDFDocument:
    document_id: str    # sha256(pdf_bytes)[:16] -- content-addressed, not a path
    filename: str
    pdf_bytes: bytes
    page_count: int
```

### Review state (`app.py`, new, browser-side)

Two small `dcc.Store`s hold only serializable metadata:

```python
# review-store: dict[document_id, dict]
{
    "<document_id>": {
        "filename": "statement.pdf",
        "page_count": 3,
        "ocr_status": "done" | "error",   # no "pending"/"running" state today —
                                            # OCR runs synchronously per click
        "ocr_error": None | "message",
        "current_page": 1,
    },
    ...
}

# review-active-store
{"document_id": "<document_id>" | None}
```

No PDF bytes, OCR text, rendered images, or model/file-handle objects ever
go into a `dcc.Store` — see section 4.

## 4. State and Caching

**Client-side (`dcc.Store`, held by the browser):**
`uploads-store` (staged upload contents, existing/unchanged design),
`review-store` and `review-active-store` (small JSON metadata only, see
above), `processed-store` / `display-store` / `selection-store` (existing,
unchanged — extracted transactions, filtered rows, and tick state).

**Server-side (`app.py` module-level dicts, held in the Python process):**

```python
_PDF_CACHE: dict[str, PDFDocument]           # document_id -> decoded PDF bytes
_OCR_CACHE: dict[str, OCRResult]             # document_id -> page-level OCR text
_PAGE_IMAGE_CACHE: dict[tuple[str, int], str]  # (document_id, page) -> base64 PNG
```

**Why server-side for these three:** a multi-page bank statement's PDF
bytes plus one rendered PNG per page easily reach several megabytes.
`dcc.Store` data is serialized into the page and held in browser memory —
fine for small metadata, wasteful and slow for binary blobs the user only
looks at one page of at a time. Keeping them server-side, keyed by
`document_id` (a content hash — see `pdf_review.make_document_id`), means
the browser only ever asks for "page N of document X" and gets exactly
that image and that page's OCR text back.

**Cache keys:** `document_id` is `sha256(pdf_bytes)[:16]` — the same file
uploaded twice gets the same id and reuses the same cache entries; the id
reveals nothing about the original filename or any server path.

**Repeated OCR/DeepSeek calls are prevented by construction, not just by
convention:**
- Page navigation (`navigate_review_page`) only mutates an integer
  (`current_page`) inside `review-store`. It never touches `_OCR_CACHE` and
  never imports `ocr_advanced` or `llm_extract`.
- `extract_transactions_step` skips any file whose name is already a key in
  `processed-store`, so clicking "Extract Transactions" or "Continue to
  Extraction" again after a successful run doesn't re-call DeepSeek.
- `render_review_panels` only re-renders an already-rendered page if
  `_PAGE_IMAGE_CACHE` doesn't have that `(document_id, page)` key yet.

**Isolation between users/sessions:** none, currently. The three caches
above are process-global, not session-scoped — every browser tab connected
to the same running `app.py` process shares them. This is acceptable for a
single-user local prototype (see `README.md`'s disclaimer) but is a real
limitation: it is **not** safe to deploy as-is to multiple concurrent users
on a shared server, since one user's uploaded statement bytes would sit in
memory (and be retrievable via a guessed/observed `document_id`) for the
lifetime of the process or until restarted. Hardening this (per-session
keys, eviction, or moving to a real cache/store) is out of scope for this
iteration — see `docs/PRODUCT_REQUIREMENTS.md` section "Out of Scope."

## 5. External Dependencies

| Dependency | Used for | Failure / fallback behaviour |
|---|---|---|
| DeepSeek (`requests`, JSON mode) | Structured transaction extraction from OCR text | No fallback — extraction for that file fails; the error is caught per-file in `extract_transactions_step` and shown in the status log, other files still process. Requires `DEEPSEEK_API_KEY`; `DEEPSEEK_API_URL` optionally overrides the default base URL (`https://api.deepseek.com/v1`). |
| Frankfurter API (`requests`) | Live FX conversion | On any exception, `fx.convert()` returns the original amount unchanged plus a warning string (1:1 fallback), rather than failing the whole extraction — unchanged by this feature. |
| docTR (`python-doctr[torch]`) | OCR | No fallback — if the model fails to load or run, the exception is caught in `run_ocr_step` and recorded as an `ocr_status: "error"` entry for that file; other files still process. Imports are function-local so a broken/missing docTR install doesn't prevent the rest of the app from loading. |
| pypdfium2 | Rendering PDF pages to images for the review panel, and (indirectly, via docTR) rasterising pages for OCR | Corrupt/empty/password-protected input raises a typed `PDFReviewError` subclass (see section 7) instead of propagating a raw `PdfiumError`. |

**Why pypdfium2 and not a new PDF-rendering library:** `python-doctr[torch]`
already depends on pypdfium2 internally (`doctr.io.DocumentFile.from_pdf`
uses it to rasterise pages for the OCR model). Calling it directly from
`src/pdf_review.py` for the review-panel preview adds no new install
weight — see the comment in `requirements.txt`.

## 6. Security and Privacy

- Bank statements contain sensitive financial data (account activity,
  merchant names, amounts). Nothing in this feature changes that risk
  profile, and this remains a **prototype**, not a hardened system.
- **No permanent storage.** Uploaded PDF bytes exist only as: (a) a
  Dash-managed base64 string in the browser's `uploads-store` while staged,
  (b) an OS temp file (`tempfile.NamedTemporaryFile`, auto-deleted on
  close) for the duration of the docTR call, and (c) the in-process
  `_PDF_CACHE` described in section 4, cleared when the app restarts.
  Nothing is written to a permanent or public directory.
- **No server filesystem paths reach the browser.** The review panel's
  image `src` is a `data:image/png;base64,...` URI built in memory; the
  document identifier exposed to the browser (`document_id`) is a content
  hash, not a path.
- **Logs do not include statement content.** Status-log lines include the
  filename and either a transaction/page count or an error message (e.g.
  "Could not read this file as a PDF: ..."), never transaction text,
  account numbers, or OCR'd page content.
- **Filenames are treated as untrusted display strings**, not used to
  construct any filesystem path (OCR still writes to a `NamedTemporaryFile`
  with a fixed `.pdf` suffix, ignoring the original name, as before this
  feature).
- **API keys stay in environment variables** (`.env`, loaded via
  `python-dotenv`, gitignored) — unchanged.
- See section 4 for the known multi-user isolation limitation.

## 7. Error Handling

| Situation | Behaviour |
|---|---|
| Invalid / corrupt PDF | `pdf_review.load_document()` raises `InvalidPDFError`; `run_ocr_step` catches it and records `ocr_status: "error"` with the message, other files keep processing. |
| Password-protected PDF | `pdf_review._open()` inspects the pypdfium2 error message for "password" and raises `PasswordProtectedPDFError` with a plain-language explanation instead of the raw PDFium error. |
| Empty PDF (0 bytes or 0 pages) | `InvalidPDFError` ("Uploaded file is empty." / "PDF has no pages."). |
| OCR failure (docTR/PyTorch exception, including docTR not being installed) | Caught by a broad `except Exception` in `run_ocr_step` (deliberately broad — docTR/PyTorch can raise many exception types we can't enumerate); recorded per-file as `ocr_status: "error"`, not swallowed, not fatal to other files. |
| Page-rendering failure | `render_page_png_base64` raises `PageOutOfRangeError` for a bad page number; `render_review_panels` catches any `PDFReviewError` from rendering and shows no image rather than crashing the callback. |
| DeepSeek failure / schema-validation failure | Caught per-file in `extract_transactions_step`; logged as `"✗ {filename}: {exc}"`, other files still process. |
| FX API failure | `fx.convert()` returns the original amount with a warning string (unchanged). |
| Export failure | Not specifically handled beyond existing pandas/openpyxl exceptions; out of scope for this iteration. |

No raw Python traceback is ever rendered in the UI — every path above
converts exceptions into a short, typed, user-facing message before it
reaches a Dash `Output`.
