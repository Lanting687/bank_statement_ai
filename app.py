"""Dash UI: drag/drop PDFs, extract + filter transactions, export to Excel."""
from __future__ import annotations

import base64
import io
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation

import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Dash, Input, Output, State, callback, ctx, dash_table, dcc, html
from dotenv import load_dotenv

from src.fx import convert
from src.pipeline import extract_statement

load_dotenv()

CURRENCY_OPTIONS = ["AUTO", "GBP", "USD", "EUR", "JPY", "AUD", "CAD", "CHF", "CNY", "INR"]

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Bank Statement AI"

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
                        dbc.Label("Minimum payment amount", className="mt-3"),
                        dbc.Input(id="threshold-input", type="number", value=50, min=0),
                        dbc.Label("Display currency", className="mt-3"),
                        dcc.Dropdown(
                            id="currency-dropdown",
                            options=[{"label": c, "value": c} for c in CURRENCY_OPTIONS],
                            value="AUTO", clearable=False,
                        ),
                        dbc.Button("Process", id="process-button", color="primary", className="mt-3 w-100"),
                        dbc.Button("Download Excel", id="download-button", color="success", className="mt-2 w-100"),
                        dcc.Download(id="download-excel"),
                        dcc.Loading(html.Div(id="status-log", className="mt-3 small")),
                        html.Div(id="fx-warning-log", className="mt-1 small text-warning"),
                    ],
                    width=4,
                ),
                dbc.Col(
                    dcc.Loading(dcc.Tabs(id="result-tabs", children=[])),
                    width=8,
                ),
            ]
        ),
        dcc.Store(id="uploads-store", data={}),
        # Raw extraction cache: {filename: {"source_currency", "transactions"}}.
        # Only written by process_uploads (OCR + Gemini) -- never touched by
        # threshold/currency changes, so re-filtering never re-runs extraction.
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
    Output("processed-store", "data"),
    Output("uploads-store", "data", allow_duplicate=True),
    Output("status-log", "children"),
    Input("process-button", "n_clicks"),
    State("uploads-store", "data"),
    State("processed-store", "data"),
    prevent_initial_call=True,
)
def process_uploads(_n_clicks, uploads, processed):
    # Pure extraction (OCR + Gemini) -- no threshold/currency here, so this
    # never needs to re-run just because the user tweaks a filter setting.
    processed = dict(processed or {})
    log_lines = []

    for filename, contents in (uploads or {}).items():
        try:
            _header, b64_data = contents.split(",", 1)
            pdf_bytes = base64.b64decode(b64_data)

            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                source_currency, transactions = extract_statement(tmp.name)

            processed[filename] = {
                "source_currency": source_currency,
                "transactions": [
                    {"date": t.date, "description": t.description, "amount": str(t.amount)}
                    for t in transactions
                ],
            }
            log_lines.append(f"✓ {filename}: {len(transactions)} transactions ({source_currency})")
        except (InvalidOperation, ValueError, OSError, KeyError) as exc:
            log_lines.append(f"✗ {filename}: {exc}")

    status = html.Ul([html.Li(line) for line in log_lines]) if log_lines else "No new files to process."
    return processed, {}, status


@callback(
    Output("display-store", "data"),
    Output("selection-store", "data"),
    Output("fx-warning-log", "children"),
    Input("processed-store", "data"),
    Input("threshold-input", "value"),
    Input("currency-dropdown", "value"),
)
def compute_display(processed, threshold, target_currency):
    # Reactive to threshold/currency: re-derives converted amounts and the
    # auto-selected baseline for every already-extracted file, with no OCR/
    # Gemini call. This is what makes the filter/currency actually take effect.
    threshold = Decimal(str(threshold)) if threshold is not None else Decimal("0")
    display: dict = {}
    selection: dict = {}
    warnings = []

    for filename, data in (processed or {}).items():
        source_currency = data["source_currency"]
        display_currency = source_currency if target_currency == "AUTO" else target_currency

        rows = []
        warning = None
        for t in data["transactions"]:
            amount = Decimal(t["amount"])
            converted_amount, fx_warning = convert(amount, source_currency, display_currency)
            warning = warning or fx_warning
            rows.append({
                "date": t["date"],
                "description": t["description"],
                "amount": str(amount),
                "converted_amount": str(converted_amount),
                "is_debit": amount < 0,
            })

        # Pre-select every debit that meets the threshold in the display
        # currency, so the user only has to sense-check / adjust, not build
        # the selection from scratch.
        selected = [
            i for i, r in enumerate(rows)
            if r["is_debit"] and -Decimal(r["converted_amount"]) >= threshold
        ]

        display[filename] = {"display_currency": display_currency, "rows": rows}
        selection[filename] = selected
        if warning:
            warnings.append(f"{filename}: {warning}")

    warning_children = html.Ul([html.Li(w) for w in warnings]) if warnings else ""
    return display, selection, warning_children


@callback(
    Output("result-tabs", "children"),
    Input("display-store", "data"),
    State("selection-store", "data"),
)
def render_tabs(display, selection):
    tabs = []
    for filename, data in (display or {}).items():
        currency = data["display_currency"]
        columns = [
            {"name": "Date", "id": "date"},
            {"name": "Description", "id": "description"},
            {"name": f"Amount ({currency})", "id": "converted_amount"},
        ]
        table = dash_table.DataTable(
            id={"type": "txn-table", "index": filename},
            columns=columns,
            data=data["rows"],
            row_selectable="multi",
            selected_rows=(selection or {}).get(filename, []),
            page_size=20,
            style_table={"overflowX": "auto"},
        )
        tabs.append(dcc.Tab(label=filename, children=[table]))
    return tabs


@callback(
    Output("selection-store", "data", allow_duplicate=True),
    Input({"type": "txn-table", "index": ALL}, "selected_rows"),
    State("selection-store", "data"),
    prevent_initial_call=True,
)
def sync_selection(_all_selected_rows, selection):
    # Tracks manual checkbox edits only -- does not feed back into
    # display-store/render_tabs, so clicking a checkbox never triggers a
    # full table rebuild.
    selection = dict(selection or {})
    for entry in ctx.inputs_list[0]:
        filename = entry["id"]["index"]
        selection[filename] = entry.get("value") or []
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
