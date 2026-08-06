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

Look at the current code (`app.py`, `src/`, `tests/`) before proposing a
redesign. Several things that look like they could be simplified are that
way on purpose — e.g. docTR/PyTorch imports are function-local in
`src/ocr_advanced.py` specifically so importing the module doesn't load
either library; `src/pdf_review.py` renders PDF pages entirely from
in-memory bytes specifically to avoid writing uploaded statements to disk.
Check `docs/ARCHITECTURE.md` for the reasoning before "fixing" something
like this.

## 3. Work only inside the active feature worktree

Do not modify the main working directory / `main` branch directly. Confirm
which worktree and branch you're on (`git status`, `git worktree list`)
before editing, and do not commit directly to `main`.

## 4. Preserve existing CLI and export behaviour

`src/cli.py` must keep working exactly as-is: `pipeline.extract_statement()`
/ `extract_transactions()` keep their original signatures, and
`src/export.py`'s CSV/JSON writers are not to be changed casually. If OCR
internals need to change again, add a new function rather than changing
the return type of an existing public one — see how
`ocr_advanced.result_to_text()` was preserved unchanged (in signature and
output) when page-level OCR was added, by building it on top of a new
`result_to_ocr_result()` instead of modifying it directly.

## 5. No external API calls from unit tests

Do not call DeepSeek, the Frankfurter FX API, or run real docTR/PyTorch
inference from `tests/`. Mock with `monkeypatch` (see `tests/test_fx.py`
for the pattern) or use fake/generated data (see `tests/test_ocr_result.py`'s
fake docTR-tree objects and `tests/test_pdf_review.py`'s in-memory
generated PDFs via `pypdfium2.PdfDocument.new()`).

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

## 8. Keep Dash callbacks thin

Callbacks in `app.py` should read/write store data and assemble outputs;
real logic belongs in `src/`. If a callback in `app.py` is doing anything
more complex than "call a `src/` function and shape the result for a Dash
`Output`," consider whether that logic belongs in `src/` instead.

## 9. Run the full test suite before finishing

```bash
pip install -r requirements.txt
pytest tests/ -q
```

Note for future Claude sessions running in a network-restricted sandbox:
if `pip install` can't reach the network, at minimum run the tests that
don't require `dash`/`doctr` to be installed
(`tests/test_filter.py`, `tests/test_fx.py`, `tests/test_parse.py`,
`tests/test_ocr_result.py`, `tests/test_pdf_review.py`, `tests/test_llm_extract.py`
— none of these import Dash or docTR at module level, and `test_llm_extract.py`
only needs `requests`/`pydantic`, both already required by other lightweight
modules), and say explicitly in your final report which tests you could and
couldn't execute, rather than claiming a full pytest run that didn't
actually happen.

## 10. Report format

When you finish a task, report:

- Files changed
- Architecture decisions (and why)
- New dependencies (and why)
- Tests added
- Test results (what actually ran, and how — see note in section 9)
- Known limitations
- Manual verification steps the user should still do (e.g. anything that
  needs a real `DEEPSEEK_API_KEY` or a real docTR install to exercise)

## 11. No unrelated refactors

Don't reformat, rename, or restructure code that isn't part of the task
you were asked to do, even if you notice something you'd do differently.
Raise it in your report instead.

## 12. Ask before introducing

Ask the user before adding any of the following — none of them exist in
this codebase today and each is a significant architectural shift:

- A database
- Authentication
- Cloud storage
- A new frontend framework (this app is Dash + dash-bootstrap-components;
  keep it that way)
- A background task queue
- Breaking changes to the CLI
- Persistent storage of uploaded statements (the current design is
  deliberately non-persistent — see `docs/ARCHITECTURE.md` section 6)
