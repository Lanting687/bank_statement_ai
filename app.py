"""
RETIRED: the Dash UI has been replaced by a Next.js frontend + FastAPI
backend (see docs/ARCHITECTURE.md).

This file is kept only because the sandbox this change was made in cannot
delete files from this mounted directory (a filesystem permission quirk,
not a design choice) -- please delete `app.py` yourself; it is no longer
imported or run by anything in this repository.

To run the application now:
    Terminal 1: uvicorn backend.main:app --reload --port 8000
    Terminal 2: cd frontend && npm install && npm run dev

`src/cli.py` is unaffected and still works exactly as before.
"""

raise SystemExit(
    "app.py (Dash) has been retired -- see docs/ARCHITECTURE.md.\n"
    "Run the backend with: uvicorn backend.main:app --reload --port 8000\n"
    "Run the frontend with: cd frontend && npm install && npm run dev\n"
    "This file can be deleted; it is not imported by anything."
)
