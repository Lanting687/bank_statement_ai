# Bank Statement AI

A human-in-the-loop Bank Statement AI Analysis Tool that extracts bank statement PDFs with different layout and formats and turns them into standardised and structurued data for easier analysis and comparision. 

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Dash](https://img.shields.io/badge/Dash-Web%20UI-008DE5)
![OCR](https://img.shields.io/badge/OCR-docTR-purple)
![Gemini](https://img.shields.io/badge/Google-Gemini-yellow)
![Pydantic](https://img.shields.io/badge/Pydantic-Structured%20Output-E92063)
![Excel](https://img.shields.io/badge/Export-Excel-217346)
![Status](https://img.shields.io/badge/Status-Prototype-orange)

## Application Preview
![Bank Statement AI interface](docs/images/bank_statement_ai_ui.png)
The interface brings the entire review workflow into one place — upload bank statements, automatically extract transactions, review AI-selected items, apply professional adjudgement, and export the final sample to Excel.

## Pain Point

- One company. Multiple bank accounts. Differnt currencies. Hundreds of pages of transactions. 
- For Unrecorded Liabilities testing, auditors may need to go through every statement, find debit transactions one by one, convert the amount and decide which payments are large enough to test. The more account, currencies and transactions are involved, the easier it is to miss an item, use the wrong exchange rate, or select payments inconsistently.
- That is the problem this tool addresses: less manual review time, fewer human errors, more consistent results.


## Key Features

- **Multi-PDF upload** — drag and drop one or multiple bank statements at once
- **AI-powered extraction** — automatically reads transactions from any PDF layout using OCR and Gemini
- **Debits only** — filters out credits so you only review payments out
- **Smart pre-selection** — rows above your minimum amount threshold are automatically ticked, so you only sense-check rather than select from scratch
- **Date range filter** — narrow the visible transactions to a specific period
- **Multi-currency support** — convert all amounts to a single currency using live exchange rates
- **Human-in-the-loop** — you stay in control; tick or untick any row before exporting
- **Excel export** — download selected transactions as a single `.xlsx` file, one sheet per statement

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web Interface | Dash | The browser UI — upload PDFs, set filters, review and download results |
| OCR | docTR | Reads text from the PDF, like a human scanning a printed page |
| AI Extraction | Gemini 2.5 Flash | Understands the text and picks out each transaction (date, amount, merchant) |
| Data Validation | Pydantic | Ensures Gemini always returns data in the exact format the app expects |
| Currency Conversion | Frankfurter API | Converts amounts to your chosen currency using live exchange rates |
| Export | pandas + openpyxl | Saves the selected transactions into an Excel file |

## How It Works

```text
Bank Statement PDF
        │
        ▼
docTR OCR
        │  1. Renders each page into a pixel image
        │  2. Detection network — draws boxes around text regions
        │  3. Recognition network — reads text inside each box
        │  4. Drops low-confidence words
        ▼
Plain Text (newline-separated, one line per text line)
        │
        ▼
Gemini 2.5 Flash
        │  Reads the plain text via system prompt instructions
        │  Ignores headers, totals, and summary lines
        │  Returns validated structured JSON
        ▼
Structured Transactions
        │  ├── date        e.g. "06 Nov 19"
        │  ├── iso_date    e.g. "2019-11-06"
        │  ├── description e.g. "TESCO STORES"
        │  ├── amount      e.g. "-62.40" (negative = debit)
        │  └── currency    e.g. "GBP"
        │
        ▼
Filter & Display (Dash Web UI)
        │  Keeps debits only
        │  Filters by date range
        │  Pre-selects rows above threshold
        ▼
User Sense-Check (tick / untick rows)
        │
        ▼
Export
        ├── Excel (.xlsx) — Web UI, checked rows only, one sheet per PDF
        └── CSV + JSON    — CLI, debits above threshold
```
