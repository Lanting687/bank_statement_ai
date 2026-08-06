# Coding Standards

Practical standards for this repository, reflecting how the existing code
(and this feature) is actually written — not a generic style guide.

## Python

- Target Python 3.11 (`python-doctr[torch]` and the rest of
  `requirements.txt` are pinned against it).
- Use type hints for public functions and data structures. Every function
  in `src/pdf_review.py` and `src/models.py` is fully annotated; follow
  that pattern for new modules.
- Prefer `@dataclass` (see `Transaction`, `OCRPage`, `OCRResult`,
  `PDFDocument`) or Pydantic models (see `llm_extract.TransactionItem`,
  `ExtractionResult`) for structured data — plain dicts are fine for
  transient Dash store payloads, but not for anything with real shape and
  behaviour.
- Keep business logic out of Dash callbacks where possible — callbacks in
  `app.py` call into `src/` and assemble the result; they don't implement
  OCR, extraction, filtering, or FX logic inline.
- Use small functions with clear responsibilities (e.g.
  `pdf_review.decode_upload` / `load_document` / `render_page_png_base64`
  are three functions, not one).
- Avoid mutable default arguments.
- Use `pathlib.Path` instead of manual path concatenation for any new
  filesystem code. (Note: existing code mostly avoids touching the
  filesystem at all where possible — `src/pdf_review.py` works entirely
  on in-memory `bytes`.)
- Catch specific exceptions where the failure mode is known (`InvalidPDFError`,
  `PasswordProtectedPDFError`, `pdfium.PdfiumError` in `pdf_review._open`).
  Broad `except Exception` is used deliberately in exactly two places
  (`run_ocr_step`, `extract_transactions_step` in `app.py`) because docTR/
  PyTorch can raise exception types this codebase doesn't enumerate, and
  `extract_transactions_step` also has to catch DeepSeek HTTP errors
  (`requests.HTTPError`), malformed JSON (`json.JSONDecodeError`), and
  schema mismatches (Pydantic `ValidationError`) in one place — both cases
  log the error per-file and continue, they never swallow it silently.
- Add docstrings to public modules, classes, and non-obvious functions —
  explain *why*, not just *what*, matching the existing style in this
  codebase (see the module docstrings in `ocr_advanced.py`, `pipeline.py`,
  `models.py`, `pdf_review.py`).
- Preserve backward compatibility unless the change is documented. Example:
  `ocr_advanced.result_to_text()` keeps its exact original signature and
  return value even though it's now implemented on top of
  `result_to_ocr_result()` — see `docs/ARCHITECTURE.md` section 3.

## Dash

- Keep layout construction separate from processing logic — `app.py`
  builds the `review_workspace` layout as a module-level value once, then
  callbacks only read/write store data and component props.
- Avoid large callbacks that perform unrelated actions. `run_ocr_step` does
  OCR only; `extract_transactions_step` does DeepSeek extraction only;
  `compute_and_render` does filtering/currency/date/table-building only —
  these are three separate callbacks, not one.
- Use `prevent_initial_call=True` on any callback that shouldn't fire on
  page load (all the new mutating callbacks do this).
- Use explicit `Input`/`Output`/`State` — no callback in this codebase
  infers dependencies implicitly.
- Avoid circular callback dependencies. The review-workspace callback graph
  is one-directional: `uploads-store` → `review-store` → (`review-doc-selector`
  → `review-active-store`) → render. Where a value needs to flow back
  (e.g. page navigation writing into `review-store`), use `no_update` to
  stop the loop rather than letting it re-trigger unrelated callbacks —
  see `sync_doc_selector`'s use of `no_update` when the active document
  hasn't changed.
- Keep expensive work out of navigation callbacks — `navigate_review_page`
  only updates an integer; it does not import or call anything from
  `ocr_advanced.py` or `llm_extract.py`.
- Use pattern-matching callbacks (`{"type": ..., "index": ALL}`) only where
  they simplify multi-item state — used for the per-file transaction
  tables (`sync_selection`) because there's a table per uploaded file. The
  document selector, by contrast, uses a plain `dcc.Dropdown` with a single
  active value, since only one document is reviewed at a time — a
  pattern-matching selector would be more code for no benefit here.
- Give components stable, descriptive ids (`review-pdf-image`,
  `review-ocr-text`, `review-page-indicator`, etc.) — no auto-generated or
  numeric ids.

## Data and Security

- Do not log raw bank statement text. Status-log lines report filenames
  and counts/error messages only — see `docs/ARCHITECTURE.md` section 6.
- Do not log API keys.
- Do not commit `.env` files (already gitignored).
- Do not expose local paths to the browser — the review panel's image
  `src` is a `data:` URI built in memory, and `document_id` is a content
  hash, never a path.
- Avoid permanent storage of uploaded PDFs — see the caching section of
  `docs/ARCHITECTURE.md`.
- Clean up temporary files — OCR still uses
  `tempfile.NamedTemporaryFile(suffix=".pdf")` as a context manager, so the
  temp file is removed as soon as the `with` block exits, same as before
  this feature.
- Validate file type and PDF parsing errors before doing anything else
  with an upload — `pdf_review.load_document()` is the single validation
  entry point; call it before OCR, not after.
- Treat filenames as untrusted input — used for display and dict keys
  only, never interpolated into a filesystem path.

## Testing

- Tests must not require DeepSeek credentials or make real HTTP calls to it
  — `tests/test_llm_extract.py` mocks `llm_extract.requests.post` via
  `monkeypatch`, the same pattern `tests/test_fx.py` uses for the FX API.
- Tests must not make real FX API calls — `tests/test_fx.py` mocks
  `fx.requests.get` / `fx.get_rate` via `monkeypatch`.
- Mock external services rather than skipping coverage for them.
- Add focused unit tests for new data structures and page-selection logic
  — see `tests/test_ocr_result.py` (OCRPage/OCRResult, and
  `result_to_ocr_result`/`result_to_text` against fake docTR-shaped
  objects) and `tests/test_pdf_review.py` (decode/validate/render, using
  PDFs generated in-memory with pypdfium2 rather than committed sample
  files).
- Add integration-level callback tests only where practical — this
  iteration verified the new `app.py` callbacks by direct invocation with
  representative fake data rather than a live Dash test server, since a
  full Dash/Selenium integration harness wasn't already part of this
  repo. Preserve and prefer this "call the callback function directly"
  pattern for new callback tests over standing up a full server.
- Preserve existing tests — `tests/test_filter.py`, `tests/test_fx.py`,
  `tests/test_parse.py` are unchanged and still pass.

## Dependencies

- Avoid adding dependencies where the standard library or an existing
  package is sufficient.
- Add dependencies only when justified, and say why in
  `requirements.txt` — see the comment above the `pypdfium2` line
  explaining it rides along with `python-doctr[torch]`'s existing
  transitive dependency rather than adding new install weight.
- Pin/constrain new dependencies consistently with the existing file
  (`>=` version floors, not exact pins).
- Update `requirements.txt` in the same change that introduces the new
  import.

## Git and Commits

- Make focused commits — one concern per commit (e.g. "add OCRResult
  model," "add PDF review module," "wire review workspace into app.py,"
  "add docs" as separate commits) rather than one commit touching
  everything.
- Do not commit generated PDFs, page images, API keys, or user data.
- Do not commit local virtual environments (`.venv/` is gitignored).
- Keep unrelated refactors separate from feature changes — this feature
  deliberately did not touch `src/filter.py`, `src/fx.py`, `src/export.py`,
  or `src/parse.py`, since none of them needed to change.
