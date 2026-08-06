# Coding Standards

Practical standards for this repository, reflecting how the existing code
is actually written — not a generic style guide. Covers both the Python
backend/pipeline and the Next.js frontend introduced in the rearchitecture
that replaced the Dash UI.

## Python (`src/`, `backend/`)

- Target Python 3.11.
- Use type hints for public functions and data structures. Every function
  in `src/pdf_review.py`, `src/models.py`, and `backend/` is fully
  annotated; follow that pattern for new modules.
- Prefer `@dataclass` (see `Transaction`, `OCRPage`, `OCRResult`,
  `PDFDocument`, `backend/store.py`'s `DocumentState`) or Pydantic models
  (see `llm_extract.TransactionItem`, `backend/schemas.py`) for structured
  data — plain dicts are fine for transient values, not for anything with
  real shape and behaviour.
- Keep FastAPI route handlers thin — same rule the old Dash callbacks
  followed. A route in `backend/main.py` should call into `src/` (or
  `backend/store.py`) and shape the result into a response model; if a
  route is doing anything more complex than that, the logic probably
  belongs in `src/` instead.
- Use small functions with clear responsibilities (e.g.
  `pdf_review.decode_upload` / `load_document` / `render_page_png_base64`
  are three functions, not one).
- Avoid mutable default arguments.
- Use `pathlib.Path` instead of manual path concatenation for any new
  filesystem code. Existing code mostly avoids touching the filesystem at
  all where possible — `src/pdf_review.py` works entirely on in-memory
  `bytes`, and `backend/store.py` never writes anything to disk.
- Catch specific exceptions where the failure mode is known
  (`InvalidPDFError`, `PasswordProtectedPDFError`,
  `pdfium.PdfiumError` in `pdf_review._open`). Broad `except Exception` is
  used deliberately in exactly two places in `backend/main.py` (the `/ocr`
  and `/extract` routes) because docTR/PyTorch and DeepSeek's HTTP client
  can each raise exception types this codebase doesn't enumerate — both
  cases record the error on the document and return a normal response
  (`ocr_status: "error"` / `502`), never swallowed silently.
- Add docstrings to public modules, classes, and non-obvious functions —
  explain *why*, not just *what*.
- Preserve backward compatibility unless the change is documented. Example:
  `ocr_advanced.result_to_text()` keeps its exact original signature and
  return value even though it's now implemented on top of
  `result_to_ocr_result()`.

## FastAPI (`backend/main.py`)

- One route, one concern. `POST /api/documents` validates and stores;
  `POST /api/documents/{id}/ocr` runs OCR; `POST /api/documents/{id}/extract`
  runs DeepSeek; `POST /api/transactions/compute` filters/converts; `POST
  /api/export/excel` builds the file. No route does two of these.
- Use plain `def`, not `async def`, for any route that does blocking,
  CPU-bound work (OCR, the DeepSeek HTTP call via `requests`) — FastAPI
  runs sync routes in a thread pool automatically, so one slow request
  doesn't stall the event loop for everyone else. Reserve `async def` for
  routes that are genuinely I/O-bound with nothing blocking (e.g.
  `upload_document`'s `await file.read()`).
- Make expensive routes idempotent by default (`run_ocr`, `extract_transactions`
  both check cached state before doing real work, with a `force` query
  param as an explicit opt-out) rather than relying on the frontend to
  avoid calling them twice.
- Raise `HTTPException` with a short, plain-language `detail` string for
  anything that should surface as an error to the user — never let a raw
  exception propagate into a 500 with a stack trace in the body.
- Response shapes are defined once, in `backend/schemas.py`, and every
  route's `response_model` uses one. Don't return raw dicts from a route
  that has a Pydantic schema available.

## TypeScript / Next.js (`frontend/`)

- App Router, one page (`app/page.tsx`) for this app's scope — don't split
  into multiple routes/pages until there's an actual reason to (e.g. a
  distinct URL a user would want to bookmark or share).
- `"use client"` at the top of any component file that uses hooks
  (`useState`, `useEffect`, `useRef`) or attaches an event handler
  (`onClick`, `onChange`) directly. Components in `components/ui/` that are
  purely presentational technically inherit client-ness from their
  importer and don't strictly need the directive, but several still
  declare it explicitly for clarity about where interactivity lives —
  don't remove it as a "cleanup."
- Keep API calls out of components — every backend call goes through
  `lib/api.ts`'s typed wrapper functions, never a raw `fetch()` scattered
  through a component. If you need a new endpoint, add a function to
  `lib/api.ts` first.
- Keep `frontend/lib/types.ts` in sync with `backend/schemas.py` by hand —
  see `docs/ARCHITECTURE.md` section 3 for why this isn't generated yet,
  and update both files in the same change when the API shape changes.
- Server-side state lives in the backend, not the frontend. Don't reach
  for `localStorage`/`sessionStorage`/cookies to persist document or
  transaction data — if it needs to survive a reload, it belongs in
  `backend/store.py`, not browser storage (this also matches
  `docs/ARCHITECTURE.md` section 6's "PDF bytes never round-trip back to
  the browser" rule — don't cache raw statement data client-side).
- Prefer composing the existing `components/ui/` primitives over adding a
  new UI dependency. If a primitive is missing something you need (e.g. a
  real Radix-based `Select` for search/multi-select), that's a deliberate
  addition to discuss, not a silent one — see "Dependencies" below.
- Use `cn()` (from `lib/utils.ts`) for any conditional className logic
  instead of manual string concatenation or template literals.

## Data and Security

- Do not log raw bank statement text, transaction descriptions, or account
  numbers, in either the backend or the frontend (e.g. no
  `console.log`-ing API responses that contain transaction data in
  committed code).
- Do not log API keys.
- Do not commit `.env` / `.env.local` files (already gitignored in both
  `requirements.txt`'s project root and `frontend/.gitignore`).
- Do not expose local/server filesystem paths to the browser —
  `document_id` is a content hash, never a path, in every API response.
- Avoid permanent storage of uploaded PDFs — see
  `docs/ARCHITECTURE.md` section 6 for the full lifecycle.
- Clean up temporary files — `backend/main.py`'s `/ocr` route still uses
  `tempfile.NamedTemporaryFile(suffix=".pdf")` as a context manager, so the
  temp file is removed as soon as the `with` block exits.
- Validate file type and PDF parsing errors before doing anything else
  with an upload — `pdf_review.load_document()` is the single validation
  entry point, called from `POST /api/documents` before anything is stored.
- Treat filenames as untrusted input — used for display and dict keys
  only, never interpolated into a filesystem path.
- CORS is scoped to the known frontend origin(s), not `allow_origins=["*"]`
  — see `backend/main.py`.

## Testing

- Tests must not require DeepSeek credentials or make real HTTP calls to
  it — `tests/test_llm_extract.py` mocks `llm_extract.requests.post`, and
  `tests/test_backend_api.py` mocks `backend.main.extract_statement_from_ocr`
  directly, both via `monkeypatch`.
- Tests must not make real FX API calls — `tests/test_fx.py` mocks
  `fx.requests.get` / `fx.get_rate`; `tests/test_backend_api.py` doesn't
  need to mock FX separately since same-currency conversion (the default
  test setup) short-circuits before any HTTP call in `src/fx.py`.
- Tests must not run real docTR/PyTorch inference —
  `tests/test_backend_api.py` mocks `backend.main.run_ocr_only`;
  `tests/test_ocr_result.py` uses fake docTR-shaped objects.
- Backend API tests use FastAPI's `TestClient` (`tests/test_backend_api.py`)
  against the real `backend/main.py` app object, with `backend/store.py`'s
  singleton cleared between tests via an autouse fixture — this exercises
  real request/response validation (Pydantic), not just the underlying
  Python functions.
- PDFs used in tests are generated in-memory with `pypdfium2.PdfDocument.new()`
  (see `tests/test_pdf_review.py`, `tests/test_backend_api.py`) rather than
  committed sample files — no real (or even synthetic-but-committed)
  financial documents in the repo.
- Preserve existing tests — `tests/test_filter.py`, `tests/test_fx.py`,
  `tests/test_parse.py` are unchanged and still pass.
- There is no frontend test suite yet (no Jest/Vitest/Playwright setup).
  If adding one, prefer testing `lib/` functions (pure, no DOM) first, and
  component/integration tests second — don't add a testing framework
  without discussing it, per "Dependencies" below.

## Dependencies

- Avoid adding dependencies where the standard library or an existing
  package is sufficient.
- Add dependencies only when justified, and say why in `requirements.txt`
  / `frontend/package.json` (as a comment or inline note near the
  addition) — see the `pypdfium2` and `httpx` comments in
  `requirements.txt` for the pattern.
- Pin/constrain new Python dependencies consistently with the existing
  file (`>=` version floors, not exact pins). Frontend dependencies in
  `package.json` follow the same convention (`^` ranges).
- Update `requirements.txt` / `frontend/package.json` in the same change
  that introduces the new import.
- The frontend intentionally has a small, easily-auditable dependency list
  (`next`, `react`, `react-dom`, `pdfjs-dist`, `clsx`, `tailwind-merge`,
  `lucide-react`, plus dev tooling). Don't add a component library
  (MUI, Ant Design, Radix, a full shadcn/ui CLI install) without checking
  whether the hand-authored `components/ui/` kit already covers the need —
  see `docs/ARCHITECTURE.md` section 2.

## Git and Commits

- Make focused commits — one concern per commit (e.g. "add FastAPI
  backend," "scaffold Next.js frontend," "add review workspace UI," "add
  docs" as separate commits) rather than one commit touching everything.
- Do not commit generated PDFs, page images, API keys, or user data.
- Do not commit local virtual environments (`.venv/`, `venv/`) or
  `node_modules/` / `.next/` (all gitignored).
- Keep unrelated refactors separate from feature changes.
