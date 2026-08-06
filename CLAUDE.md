# Instructions for Claude Code sessions on this repository

This file is for future Claude Code sessions working on Bank Statement AI.
Read it before making changes.

## 1. Read these first

Before editing anything, read:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/CODING_STANDARDS.md`

These describe the actual implementation, not aspirational design — keep
them in sync with any change you make.

## 2. Inspect before proposing architecture changes

Look at the current code (`backend/`, `frontend/`, `src/`, `tests/`) before
proposing a redesign. Several things that look like they could be
simplified are that way on purpose — e.g. docTR/PyTorch imports are
function-local in `src/ocr_advanced.py` specifically so importing the
module doesn't load either library; PDF page rendering happens client-side
in `frontend/components/pdf-page-viewer.tsx` via `pdf.js` specifically so
the backend never needs to produce or cache preview images (see
`docs/ARCHITECTURE.md` section 4 for the trade-off that was accepted to
get that); `backend/main.py`'s OCR/extraction routes are deliberately
idempotent rather than relying on the frontend to avoid duplicate calls.
Check `docs/ARCHITECTURE.md` for the reasoning before "fixing" something
like this.

**Stack, as of this rearchitecture:** Next.js (App Router, TypeScript,
Tailwind CSS) frontend in `frontend/`, talking over HTTP to a FastAPI
backend in `backend/`, which wraps the same `src/` pipeline the CLI uses.
The previous Dash app (`app.py`) has been retired — do not resurrect it or
add new features to it; it should be deleted (see the note at the top of
that file for why it still exists as a file).

## 3. Work only inside the active feature worktree

Do not modify the main working directory / `main` branch directly. Confirm
which worktree and branch you're on (`git status`, `git worktree list`)
before editing, and do not commit directly to `main`.

## 4. Preserve existing CLI and export behaviour

`src/cli.py` must keep working exactly as-is, independent of
`backend`/`frontend` entirely: `pipeline.extract_statement()` /
`extract_transactions()` keep their original signatures, and
`src/export.py`'s CSV/JSON writers are not to be changed casually. If OCR
internals need to change again, add a new function rather than changing
the return type of an existing public one — see how
`ocr_advanced.result_to_text()` was preserved unchanged (in signature and
output) when page-level OCR was added, by building it on top of
`result_to_ocr_result()` instead of modifying it directly.

## 5. No external calls from tests

Do not call DeepSeek, the Frankfurter FX API, run real docTR/PyTorch
inference, or start a real `uvicorn`/`next dev` server from `tests/`. Mock
with `monkeypatch` (see `tests/test_fx.py`, `tests/test_llm_extract.py` for
the pattern) or use fake/generated data (see `tests/test_ocr_result.py`'s
fake docTR-tree objects, `tests/test_pdf_review.py` and
`tests/test_backend_api.py`'s in-memory generated PDFs via
`pypdfium2.PdfDocument.new()`). `tests/test_backend_api.py` uses FastAPI's
`TestClient` against the real app object — that's an in-process test
client, not a real running server, and is fine.

## 6. Do not commit sensitive data

Do not add API keys, uploaded bank statements, OCR output, or any real
financial data to Git. Generate synthetic/blank test fixtures in code
instead of committing files with real transaction data.

## 7. Keep pipeline stages as separate concerns

OCR (`src/ocr_advanced.py`), LLM extraction (`src/llm_extract.py`),
filtering (`src/filter.py`), FX conversion (`src/fx.py`), and export
(`src/export.py`) are separate modules for a reason — each is independently
testable and independently swappable. `src/pipeline.py` is the only module
that's allowed to know about more than one of them at once.
`backend/main.py` may call into more than one (it's the new equivalent of
what Dash callbacks used to do), but should stay thin — see rule 8.

## 8. Keep API routes and frontend components thin

Routes in `backend/main.py` should read/write `backend/store.py` state and
assemble a response; real logic belongs in `src/`. Frontend components in
`frontend/components/` should be presentational; API calls belong in
`frontend/lib/api.ts`, not scattered `fetch()` calls inside components. If
a route or component is doing anything more complex than that, consider
whether the logic belongs elsewhere.

## 9. Run the full test suite before finishing

```bash
pip install -r requirements.txt
pytest tests/ -q
```

Note for future Claude sessions running in a network-restricted sandbox:
if `pip install` can't reach the network (or `npm install` can't, for
frontend changes), at minimum run/verify the tests that don't require
`fastapi`/`doctr`/etc. to be installed (`tests/test_filter.py`,
`tests/test_fx.py`, `tests/test_parse.py`, `tests/test_ocr_result.py`,
`tests/test_pdf_review.py`, `tests/test_llm_extract.py` — none of these
import FastAPI or docTR at module level), and say explicitly in your final
report which tests you could and couldn't actually execute, and what you
did instead to verify (e.g. direct function-level invocation with stub
modules), rather than claiming a full pytest/npm run that didn't actually
happen.

## 10. Report format

When you finish a task, report:

- Files changed
- Architecture decisions (and why)
- New dependencies (and why)
- Tests added
- Test results (what actually ran, and how — see note in section 9)
- Known limitations
- Manual verification steps the user should still do (e.g. anything that
  needs a real `DEEPSEEK_API_KEY`, a real docTR install, or `npm
  install`/`npm run dev` to exercise)

## 11. No unrelated refactors

Don't reformat, rename, or restructure code that isn't part of the task
you were asked to do, even if you notice something you'd do differently.
Raise it in your report instead.

## 12. Ask before introducing

Ask the user before adding any of the following:

- A database
- Authentication
- Cloud storage
- A component library / design system beyond the current hand-authored
  `frontend/components/ui/` kit (Material UI, Ant Design, a full shadcn/ui
  CLI + Radix install) — see `docs/CODING_STANDARDS.md`
- A background task queue
- Breaking changes to the CLI
- Persistent storage of uploaded statements (the current design is
  deliberately non-persistent — see `docs/ARCHITECTURE.md` section 6)
- Generating `frontend/lib/types.ts` from the backend's OpenAPI schema (a
  reasonable idea, but a build-process change someone should sign off on
  — see `docs/ARCHITECTURE.md` section 3)

The Next.js + FastAPI split itself was an explicit, discussed decision
(see `docs/PRODUCT_REQUIREMENTS.md`) — it does not need to be re-asked
about, but further major stack changes on top of it do.
