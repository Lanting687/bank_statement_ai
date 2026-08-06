"""Dash UI: drag/drop PDFs, review OCR against the original page, extract +
filter transactions, export to Excel.

Workflow: upload -> Run OCR -> review PDF/OCR side by side -> Extract
Transactions (DeepSeek) -> filter/review transactions -> export.

Server-side caches (see _PDF_CACHE / _OCR_CACHE / _PAGE_IMAGE_CACHE below):
uploaded PDF bytes, OCR results, and rendered page images are kept in
process memory, keyed by a content-hash document_id, rather than round-
tripped through dcc.Store. dcc.Store data is sent to and held by the
browser, so putting multi-megabyte PDF/image blobs there for every
uploaded statement would bloat every page-navigation request for no
reason -- the browser only ever needs the current page's rendered image
and OCR text, not every page of every uploaded file at once. See
docs/ARCHITECTURE.md section "State and Caching" for the full rationale
and its limitations (single-process only; not multi-worker safe).
"""
from __future__ import annotations

import io
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation

import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback, ctx, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv

from src import pdf_review
from src.filter import in_date_range
from src.fx import convert
from src.pdf_review import PDFDocument
from src.pipeline import extract_statement_from_ocr, run_ocr_only

load_dotenv()

CURRENCY_OPTIONS = ["AUTO", "GBP", "USD", "EUR", "JPY", "AUD", "CAD", "CHF", "CNY", "INR"]

# Server-side, process-lifetime caches keyed by document_id (a content hash,
# not a filesystem path -- see src/pdf_review.make_document_id). Holds the
# decoded PDF bytes, the OCRResult, and rendered page images so OCR/DeepSeek
# never re-run and pages aren't re-rendered on every navigation click.
# Prototype-scale only: in-process memory, cleared on restart, shared across
# any browser session connected to this process. Not safe for a multi-worker
# or multi-user deployment -- see docs/ARCHITECTURE.md.
_PDF_CACHE: dict[str, PDFDocument] = {}
_OCR_CACHE: dict[str, object] = {}  # document_id -> OCRResult
_PAGE_IMAGE_CACHE: dict[tuple[str, int], str] = {}  # (document_id, page) -> base64 PNG

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Bank Statement AI"

review_workspace = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(id="review-doc-selector", options=[], placeholder="Select a document to review"),
                    xs=12, md=8,
                ),
                dbc.Col(html.Div(id="review-doc-status", className="small text-muted mt-2 mt-md-0"), xs=12, md=4),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H6("Original PDF"),
                        html.Div(
                            html.Img(id="review-pdf-image", style={"width": "100%"}),
                            style={"maxHeight": "70vh", "overflowY": "auto", "border": "1px solid #dee2e6"},
                        ),
                    ],
                    xs=12, md=6, className="mb-3",
                ),
                dbc.Col(
                    [
                        html.H6("OCR Extracted Text"),
                        html.Pre(
                            id="review-ocr-text",
                            style={
                                "maxHeight": "70vh", "overflowY": "auto",
                                "whiteSpace": "pre-wrap", "fontFamily": "monospace",
                                "border": "1px solid #dee2e6", "padding": "0.5rem",
                                "backgroundColor": "#f8f9fa",
                            },
                        ),
                    ],
                    xs=12, md=6, className="mb-3",
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(dbc.Button("Previous", id="review-prev-button", outline=True, className="w-100"), xs=4, md=2),
                dbc.Col(html.Div(id="review-page-indicator", className="text-center mt-2"), xs=4, md=4),
                dbc.Col(dbc.Button("Next", id="review-next-button", outline=True, className="w-100"), xs=4, md=2),
                dbc.Col(
                    dbc.Button("Continue to Extraction", id="review-continue-button", color="primary", className="w-100"),
                    xs=12, md=4, className="mt-2 mt-md-0",
                ),
            ],
            className="align-items-center",
        ),
    ]
)

app.layout = dbc.Container(
    [
        html.H3("Bank Statement AI", className="my-3"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Upload(
                            id="pdf-upload",
                            children=html.Div("Drag and drop PDF(s) here, or click to select"),
                            multiple=True,
                            accept=".pdf",
                            style={
                                "width": "100%", "height": "90px", "lineHeight": "90px",
                                "borderWidth": "1px", "borderStyle": "dashed",
                                "borderRadius": "8px", "textAlign": "center",
                            },
                        ),
                        html.Div(id="pending-files-list", className="my-2"),
                        dbc.Button("Run OCR", id="run-ocr-button", color="secondary", className="mt-1 w-100"),
                        dbc.Label("Minimum payment amount", className="mt-3"),
                        dbc.Input(id="threshold-input", type="number", value=50, min=0),
                        dbc.Label("Date range", className="mt-3"),
                        html.Div(
                            dcc.DatePickerRange(
                                id="date-range-picker",
                                start_date=None,
                                end_date=None,
                                clearable=True,
                                display_format="YYYY-MM-DD",
                            ),
                        ),
                        dbc.Label("Display currency", className="mt-3"),
                        dcc.Dropdown(
                            id="currency-dropdown",
                            options=[{"label": c, "value": c} for c in CURRENCY_OPTIONS],
                            value="AUTO", clearable=False,
                        ),
                        dbc.Button("Extract Transactions", id="extract-button", color="primary", className="mt-3 w-100"),
                        dbc.Button("Download Excel", id="download-button", color="success", className="mt-2 w-100"),
                        dcc.Download(id="download-excel"),
                        dcc.Loading(html.Div(id="status-log", className="mt-3 small")),
                        html.Div(id="fx-warning-log", className="mt-1 small text-warning"),
                    ],
                    xs=12, md=4,
                ),
                dbc.Col(
                    dcc.Tabs(
                        id="main-tabs",
                        value="tab-review",
                        children=[
                            dcc.Tab(label="Review OCR", value="tab-review", children=[review_workspace]),
                            dcc.Tab(
                                label="Transactions", value="tab-transactions",
                                children=[dcc.Loading(dcc.Tabs(id="result-tabs", children=[]))],
                            ),
                        ],
                    ),
                    xs=12, md=8,
                ),
            ]
        ),
        dcc.Store(id="uploads-store", data={}),
        # Per-document review metadata (small, serializable): filename, page
        # count, OCR status, and which page is currently being viewed. The
        # actual PDF bytes / OCR text / rendered images stay server-side in
        # the caches above and are looked up by document_id.
        dcc.Store(id="review-store", data={}),
        # Which document is selected in the review workspace right now.
        dcc.Store(id="review-active-store", data={}),
        # Raw extraction cache: {filename: {"source_currency", "transactions"}}.
        # Only written by extract_transactions_step (DeepSeek) -- never touched
        # by threshold/currency changes, so re-filtering never re-runs extraction.
        dcc.Store(id="processed-store", data={}),
        # Derived, recomputed any time processed-store / threshold / currency
        # change: {filename: {"display_currency", "rows": [...with converted_amount/is_debit]}}.
        dcc.Store(id="display-store", data={}),
        # Which row indices are checked per file. Reset to the auto threshold
        # match whenever display-store recomputes; updated live by checkbox clicks.
        dcc.Store(id="selection-store", data={}),
    ],
    fluid=True,
)


def _sheet_name(filename: str) -> str:
    name = re.sub(r"[\\/*?:\[\]]", "_", os.path.splitext(filename)[0])
    return name[:31] or "sheet"


@callback(
    Output("uploads-store", "data"),
    Output("pending-files-list", "children"),
    Input("pdf-upload", "contents"),
    Input("pdf-upload", "filename"),
    State("uploads-store", "data"),
)
def stage_uploads(contents_list, filename_list, uploads):
    uploads = dict(uploads or {})
    if contents_list and filename_list:
        for filename, contents in zip(filename_list, contents_list):
            uploads[filename] = contents
    items = [html.Li(name) for name in uploads]
    return uploads, html.Ul(items) if items else html.Div("No files queued.")


@callback(
    Output("review-store", "data"),
    Output("uploads-store", "data", allow_duplicate=True),
    Output("status-log", "children"),
    Input("run-ocr-button", "n_clicks"),
    State("uploads-store", "data"),
    State("review-store", "data"),
    prevent_initial_call=True,
)
def run_ocr_step(_n_clicks, uploads, review):
    # OCR only -- no DeepSeek call here, so re-running this never re-triggers
    # transaction extraction. Runs once per uploaded file; the resulting
    # OCRResult is cached in _OCR_CACHE and reused by both the review panel
    # (page by page) and, later, extract_transactions_step (DeepSeek).
    review = dict(review or {})
    log_lines = []

    for filename, contents in (uploads or {}).items():
        try:
            pdf_bytes = pdf_review.decode_upload(contents)
            doc = pdf_review.load_document(filename, pdf_bytes)
            _PDF_CACHE[doc.document_id] = doc

            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                ocr_result = run_ocr_only(tmp.name)
            _OCR_CACHE[doc.document_id] = ocr_result

            review[doc.document_id] = {
                "filename": filename,
                "page_count": doc.page_count,
                "ocr_status": "done",
                "ocr_error": None,
                "current_page": 1,
            }
            log_lines.append(f"✓ {filename}: OCR complete ({doc.page_count} page(s))")
        except pdf_review.PDFReviewError as exc:
            review[f"error::{filename}"] = {
                "filename": filename, "page_count": 0,
                "ocr_status": "error", "ocr_error": str(exc), "current_page": 1,
            }
            log_lines.append(f"✗ {filename}: {exc}")
        except Exception as exc:
            # docTR/PyTorch can raise many different exception types we
            # can't enumerate; still recorded per-document, not swallowed.
            review[f"error::{filename}"] = {
                "filename": filename, "page_count": 0,
                "ocr_status": "error", "ocr_error": str(exc), "current_page": 1,
            }
            log_lines.append(f"✗ {filename}: OCR failed ({exc})")

    status = html.Ul([html.Li(line) for line in log_lines]) if log_lines else "No new files to process."
    return review, {}, status


@callback(
    Output("review-doc-selector", "options"),
    Output("review-doc-selector", "value"),
    Input("review-store", "data"),
    State("review-doc-selector", "value"),
)
def sync_doc_selector(review, current_value):
    review = review or {}
    options = [
        {"label": f"{meta['filename']} ({meta['ocr_status']})", "value": doc_id}
        for doc_id, meta in review.items()
    ]
    if current_value in review:
        # Active document is still present -- don't force a re-select, which
        # would otherwise bounce the review panels back to page 1.
        return options, no_update
    return options, next(iter(review), None)


@callback(
    Output("review-active-store", "data"),
    Input("review-doc-selector", "value"),
)
def set_active_document(doc_id):
    return {"document_id": doc_id}


@callback(
    Output("review-store", "data", allow_duplicate=True),
    Input("review-prev-button", "n_clicks"),
    Input("review-next-button", "n_clicks"),
    State("review-active-store", "data"),
    State("review-store", "data"),
    prevent_initial_call=True,
)
def navigate_review_page(_prev, _next, active, review):
    # Page navigation only ever updates an integer in review-store; it never
    # touches _OCR_CACHE or calls OCR/DeepSeek/FX.
    review = dict(review or {})
    doc_id = (active or {}).get("document_id")
    if not doc_id or doc_id not in review:
        raise PreventUpdate

    meta = dict(review[doc_id])
    page = meta.get("current_page", 1)
    page_count = meta.get("page_count", 1) or 1

    if ctx.triggered_id == "review-prev-button":
        page = max(1, page - 1)
    elif ctx.triggered_id == "review-next-button":
        page = min(page_count, page + 1)

    meta["current_page"] = page
    review[doc_id] = meta
    return review


@callback(
    Output("review-pdf-image", "src"),
    Output("review-ocr-text", "children"),
    Output("review-page-indicator", "children"),
    Output("review-doc-status", "children"),
    Input("review-active-store", "data"),
    Input("review-store", "data"),
)
def render_review_panels(active, review):
    review = review or {}
    doc_id = (active or {}).get("document_id")

    if not doc_id or doc_id not in review:
        return None, "Upload a PDF and click Run OCR to begin reviewing.", "", ""

    meta = review[doc_id]
    status = meta.get("ocr_status")

    if status == "error":
        return None, f"OCR failed: {meta.get('ocr_error', 'unknown error')}", "", "OCR unavailable"

    page = meta.get("current_page", 1)
    page_count = meta.get("page_count", 0)

    img_src = None
    pdf_doc = _PDF_CACHE.get(doc_id)
    if pdf_doc is not None and page_count:
        cache_key = (doc_id, page)
        png_b64 = _PAGE_IMAGE_CACHE.get(cache_key)
        if png_b64 is None:
            try:
                png_b64 = pdf_review.render_page_png_base64(pdf_doc.pdf_bytes, page)
                _PAGE_IMAGE_CACHE[cache_key] = png_b64
            except pdf_review.PDFReviewError:
                png_b64 = None
        if png_b64:
            img_src = f"data:image/png;base64,{png_b64}"

    ocr_result = _OCR_CACHE.get(doc_id)
    ocr_page = ocr_result.page(page) if ocr_result is not None else None
    if ocr_page is None:
        ocr_text = "OCR unavailable for this page."
    elif not ocr_page.text:
        ocr_text = "No text recognised on this page."
    else:
        ocr_text = ocr_page.text

    indicator = f"Page {page} of {page_count}" if page_count else ""
    doc_status = "OCR complete" if status == "done" else "Processing OCR" if status == "running" else "OCR unavailable"
    return img_src, ocr_text, indicator, doc_status


@callback(
    Output("processed-store", "data"),
    Output("status-log", "children", allow_duplicate=True),
    Output("main-tabs", "value"),
    Input("extract-button", "n_clicks"),
    Input("review-continue-button", "n_clicks"),
    State("review-store", "data"),
    State("processed-store", "data"),
    prevent_initial_call=True,
)
def extract_transactions_step(_n1, _n2, review, processed):
    # DeepSeek extraction, run once per document against its cached OCRResult
    # -- never re-runs OCR, and skips any file already in processed-store so
    # clicking either "Extract Transactions" or "Continue to Extraction"
    # again doesn't re-call DeepSeek for files already extracted.
    processed = dict(processed or {})
    review = review or {}
    log_lines = []

    for doc_id, meta in review.items():
        filename = meta["filename"]
        if meta.get("ocr_status") != "done":
            continue
        if filename in processed:
            continue

        ocr_result = _OCR_CACHE.get(doc_id)
        if ocr_result is None:
            log_lines.append(f"✗ {filename}: OCR result no longer available -- click Run OCR again")
            continue

        try:
            source_currency, transactions = extract_statement_from_ocr(ocr_result)
            processed[filename] = {
                "source_currency": source_currency,
                "transactions": [
                    {
                        "date": t.date,
                        "iso_date": t.iso_date,
                        "description": t.description,
                        "amount": str(t.amount),
                    }
                    for t in transactions
                ],
            }
            log_lines.append(f"✓ {filename}: {len(transactions)} transactions ({source_currency})")
        except Exception as exc:
            log_lines.append(f"✗ {filename}: {exc}")

    status = html.Ul([html.Li(line) for line in log_lines]) if log_lines else "No documents ready for extraction."
    return processed, status, "tab-transactions"


@callback(
    Output("result-tabs", "children"),
    Output("display-store", "data"),
    Output("selection-store", "data"),
    Output("fx-warning-log", "children"),
    Input("processed-store", "data"),
    Input("threshold-input", "value"),
    Input("currency-dropdown", "value"),
    Input("date-range-picker", "start_date"),
    Input("date-range-picker", "end_date"),
)
def compute_and_render(processed, threshold, target_currency, start_date, end_date):
    # Single callback: compute rows + selection + build tabs all at once.
    # selected_rows is passed directly to DataTable without going through
    # any intermediate store, eliminating every possible timing gap.
    threshold_f = float(threshold) if threshold is not None else 0.0
    tabs = []
    display: dict = {}
    selection: dict = {}
    warnings = []

    for filename, data in (processed or {}).items():
        source_currency = data["source_currency"]
        display_currency = source_currency if target_currency == "AUTO" else target_currency

        all_rows = []
        warning = None

        for t in data["transactions"]:
            amount = Decimal(t["amount"])
            if amount >= 0:
                continue  # show paid-out only
            converted_amount, fx_warning = convert(amount, source_currency, display_currency)
            warning = warning or fx_warning
            all_rows.append({
                "date": t["date"],
                "iso_date": t.get("iso_date", ""),
                "description": t["description"],
                "converted_amount": str(converted_amount),
            })

        # Only show rows within the selected date range (all rows shown when picker is blank).
        rows = [r for r in all_rows if in_date_range(r["iso_date"], start_date, end_date)]

        # Pre-select rows above threshold; date is already enforced by the row filter above.
        selected = [
            i for i, r in enumerate(rows)
            if abs(float(r["converted_amount"])) >= threshold_f
        ]

        # Tag each row so style_data_conditional can use filter_query instead of
        # row_index. row_index is page-local on page 2+, causing highlights to
        # land on the wrong rows; filter_query operates on data values and is
        # always correct regardless of page.
        selected_set = set(selected)
        for i, r in enumerate(rows):
            r["_sel"] = "1" if i in selected_set else "0"

        columns = [
            {"name": "Date", "id": "date"},
            {"name": "Description", "id": "description"},
            {"name": f"Amount ({display_currency})", "id": "converted_amount"},
        ]
        table = dash_table.DataTable(
            id={"type": "txn-table", "index": filename},
            columns=columns,
            data=rows,
            row_selectable="multi",
            selected_rows=selected,
            page_size=20,
            style_table={"overflowX": "auto"},
            style_data_conditional=[
                {
                    "if": {"filter_query": '{_sel} = "1"'},
                    "backgroundColor": "#d4edda",
                    "fontWeight": "600",
                }
            ],
        )
        tabs.append(dcc.Tab(label=filename, children=[table]))

        display[filename] = {"display_currency": display_currency, "rows": rows}
        selection[filename] = selected
        if warning:
            warnings.append(f"{filename}: {warning}")

    warning_children = html.Ul([html.Li(w) for w in warnings]) if warnings else ""
    return tabs, display, selection, warning_children


@callback(
    Output("selection-store", "data", allow_duplicate=True),
    Input({"type": "txn-table", "index": ALL}, "selected_rows"),
    State("selection-store", "data"),
    prevent_initial_call=True,
)
def sync_selection(_all_selected_rows, selection):
    selection = dict(selection or {})
    for entry in ctx.inputs_list[0]:
        filename = entry["id"]["index"]
        value = entry.get("value") or []
        selection[filename] = value
    return selection


@callback(
    Output("download-excel", "data"),
    Input("download-button", "n_clicks"),
    State("display-store", "data"),
    State("selection-store", "data"),
    prevent_initial_call=True,
)
def download_excel(_n_clicks, display, selection):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for filename, data in (display or {}).items():
            selected = set((selection or {}).get(filename, []))
            rows = [r for i, r in enumerate(data["rows"]) if i in selected]
            df = pd.DataFrame(rows, columns=["date", "description", "converted_amount"])
            df.columns = ["Date", "Description", f"Amount ({data['display_currency']})"]
            df.to_excel(writer, sheet_name=_sheet_name(filename), index=False)
    buf.seek(0)
    return dcc.send_bytes(buf.read(), "transactions.xlsx")


if __name__ == "__main__":
    app.run(debug=True)
