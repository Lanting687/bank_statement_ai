# Bank Statement AI

A human-in-the-loop Bank statement AI analysis tool that extracts bank statement PDFs with different layout and formats and turn them into standardised and structurued data for easier analysis and comparision. 

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Dash](https://img.shields.io/badge/Dash-Web%20UI-008DE5)
![OCR](https://img.shields.io/badge/OCR-docTR-purple)
![Gemini](https://img.shields.io/badge/Google-Gemini-yellow)
![Pydantic](https://img.shields.io/badge/Pydantic-Structured%20Output-E92063)
![Excel](https://img.shields.io/badge/Export-Excel-217346)
![Status](https://img.shields.io/badge/Status-Prototype-orange)

## Live Demo

Live deployment is not currently available.

A local version can be run by following the instructions in the
[Running Locally](#running-locally) section.

<!-- Replace this with your own application screenshot -->

![Bank Statement AI Interface](docs/images/app-preview.png)

## Pain Point

- One company. Multiple bank accounts. Differnt currencies. Hundreds of pages of transactions. 
- For Unrecorded Liabilities testing, auditors may need to go through every statement, find debit transactions one by one, convert the amount and decide which payments are large enough to test.
-The more account and currencies a company has, the easier there are human error.
- That is the problem this tool address: less manual review time, less human error, more consistent results.


## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web Interface | Dash | Upload, filter, and transaction review UI |
| OCR | docTR | Text extraction from scanned and digital PDFs |
| LLM | Gemini 2.5 Flash | Structured transaction extraction from OCR text |
| Validation | Pydantic | Enforces JSON output schema from Gemini |
| FX Conversion | Frankfurter API | Live exchange rates for multi-currency conversion |
| Export | pandas + openpyxl | Multi-sheet Excel workbook generation |

## How It Works

```text
Bank Statement PDF
        │
        ▼
docTR OCR
        │
        │  Extracts text from scanned or digital PDFs
        ▼
Plain Text
        │
        ▼
Gemini 2.5 Flash
        │
        │  Returns validated structured JSON
        ▼
Transactions
        │
        ├── date
        ├── description
        ├── signed amount
        └── currency
        │
        ▼
Dash Web UI / CLI
        │
        ▼
Excel / CSV / JSON
```

