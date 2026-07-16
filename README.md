# Bank Statement AI

A human-in-the-loop Bank statement AI analysis too that extracts bank statement PDFs with different layout and formats and turn them into standardised and structurued data for easier analysis and comparision. 

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

- Bank statements are often provided as PDFs with inconsistent layouts and formats.
- Some statements contain selectable text, while others are scanned documents that require OCR.
- Manually identifying debit transactions and transferring them into Excel is repetitive and time-consuming.
- High-value transactions often require additional review, but manually filtering and selecting them increases the risk of omissions.
- Reviewers need a clear way to sense-check extracted transactions before relying on the output.
- Traditional rule-based extraction can be difficult to maintain across different banks and statement formats.

Bank Statement AI addresses these issues by combining OCR, structured LLM extraction and a human-in-the-loop review interface.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web Interface | Dash, Python | Provides the upload, filtering and transaction review interface |
| OCR | docTR | Extracts text from scanned and digital bank statement PDFs |
| LLM | Gemini 2.5 Flash | Converts unstructured OCR text into structured transaction records |
| Validation | Pydantic | Enforces the expected structured output schema |
| Data Processing | Python, pandas | Cleans, filters and transforms extracted transactions |
| PDF Processing | docTR PDF utilities | Processes multi-page PDF documents |
| FX Conversion | Frankfurter API | Retrieves live foreign exchange rates when conversion is required |
| Export | pandas, openpyxl | Creates Excel workbooks containing selected transactions |
| CLI | Python argparse | Supports scripted and single-file processing |
| Version Control | Git, GitHub | Manages source code and project history |

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

The processing pipeline is:

1. The user uploads a bank statement PDF or supplies a PDF path through the CLI.
2. docTR extracts text from each page of the document.
3. The extracted text is sent to Gemini with a predefined Pydantic schema.
4. Gemini converts the text into structured transaction records.
5. Transaction dates and amounts are standardised.
6. Debit and credit transactions are identified using their signed amounts.
7. The user reviews debit transactions in the web interface.
8. Selected transactions are exported to Excel.

## Amount Convention

Gemini assigns signed amounts using the following convention:

| Transaction type | Stored amount |
|---|---:|
| Debit | Negative |
| Credit | Positive |

For example:

```json
{
  "date": "12/05/2026",
  "description": "CARD PAYMENT TO EXAMPLE STORE",
  "amount": -125.50,
  "currency": "GBP"
}
```

This convention drives all downstream filtering.

The web interface only displays transactions where:

```python
transaction.amount < 0
```

Debit amounts may be displayed as positive values in the interface for easier review, while the underlying extracted value remains negative.

## Key Features

### PDF Upload

- Supports drag-and-drop PDF uploads.
- Accepts multiple bank statements in one session.
- Processes both scanned and digitally generated statements.
- Keeps transactions separated by source PDF.

### AI-Powered Extraction

- Uses docTR for deep-learning OCR.
- Uses Gemini 2.5 Flash for structured transaction extraction.
- Returns transaction data using a validated Pydantic schema.
- Extracts dates, descriptions, signed amounts and currencies.
- Reduces reliance on bank-specific parsing rules.

### Debit Transaction Review

Only debit transactions are displayed in the web interface.

Credits are discarded before the review table is rendered.

This allows the user to focus on outgoing payments that may require further testing or investigation.

### Date Range Filtering

The date picker controls which transactions are visible in the table.

When a date range is selected:

- transactions inside the range remain visible;
- transactions outside the range are hidden;
- threshold selection is applied only to the visible transactions.

When the date picker is blank, all extracted debit transactions are displayed.

### Threshold-Based Pre-Selection

The minimum amount threshold automatically pre-selects visible transactions above the selected value.

Transactions meeting the threshold are:

- ticked by default;
- highlighted in green;
- included in the Excel export unless manually deselected.

The threshold affects selection rather than visibility.

For example, if the minimum amount is set to `£1,000`:

```text
£2,500 debit  → visible and selected
£1,200 debit  → visible and selected
£450 debit    → visible but not selected
```

### Human-in-the-Loop Review

The application does not export extracted results automatically.

Instead, the user can:

- inspect extracted transaction details;
- sense-check descriptions and amounts;
- tick missing rows;
- untick incorrectly selected rows;
- review the final sample before export.

This creates a review step between AI extraction and final output.

### Excel Export

The Excel download contains only checked transactions.

For multiple uploaded PDFs:

- one workbook is generated;
- each source PDF receives its own worksheet;
- only selected transactions are included;
- worksheet names are derived from the source file names.

## Interfaces

The project provides two ways to process statements.

| Feature | Web UI | CLI |
|---|---|---|
| Entry point | `app.py` | `src/cli.py` |
| Input | One or multiple PDFs | Single PDF path |
| Review table | Yes | No |
| Date filtering | Yes | No |
| Threshold selection | Yes | Yes |
| Manual selection | Yes | No |
| Excel output | Yes | No |
| CSV output | No | Yes |
| JSON output | No | Yes |
| Intended use | Review and sense-checking | Scripted or batch processing |

## Running Locally

### Prerequisites

You will need:

- Python 3.11 or later
- A Google Gemini API key
- Git
- A virtual environment
- Internet access for Gemini and optional FX conversion

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Replace the repository URL with the actual GitHub repository URL.

### 2. Create a Virtual Environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The first docTR run may download the required OCR model weights.

### 4. Create an Environment File

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Do not commit the `.env` file to GitHub.

Confirm that `.env` is included in `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.pyc
output/
```

### 5. Start the Web Application

```bash
python app.py
```

Open the local address shown in the terminal, normally:

```text
http://127.0.0.1:8050
```

## Using the Web Interface

1. Open the application in your browser.
2. Drag and drop one or more bank statement PDFs.
3. Wait for OCR and Gemini extraction to complete.
4. Select the required statement date range.
5. Enter the minimum debit threshold.
6. Review the automatically selected transactions.
7. Tick or untick rows as required.
8. Select **Download Excel**.
9. Open the generated workbook and review the selected transactions.

## Using the CLI

Run the CLI with a PDF path:

```bash
python -m src.cli path/to/bank_statement.pdf
```

Example:

```bash
python -m src.cli samples/example_statement.pdf
```

The CLI processes one statement and generates:

```text
transactions.csv
transactions.json
```

Depending on the CLI configuration, an amount threshold can also be supplied.

Example:

```bash
python -m src.cli samples/example_statement.pdf --threshold 1000
```

## Project Structure

```text
bank-statement-ai/
│
├── app.py
├── requirements.txt
├── README.md
├── .env
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── ocr_advanced.py
│   ├── llm_extract.py
│   ├── parse.py
│   ├── fx.py
│   ├── filter.py
│   └── export.py
│
├── docs/
│   └── images/
│       └── app-preview.png
│
├── samples/
│   └── example_statement.pdf
│
└── output/
    ├── transactions.csv
    └── transactions.json
```

## Key Source Files

| File | Responsibility |
|---|---|
| `app.py` | Dash application for PDF upload, filtering, review and Excel export |
| `src/pipeline.py` | Coordinates the complete OCR-to-transaction extraction workflow |
| `src/ocr_advanced.py` | Wraps docTR and converts PDFs into text with optional bounding-box information |
| `src/llm_extract.py` | Sends OCR text to Gemini and validates the structured response |
| `src/parse.py` | Defines and standardises the `Transaction` data model |
| `src/fx.py` | Retrieves foreign exchange rates from the Frankfurter API |
| `src/filter.py` | Applies the CLI transaction threshold |
| `src/export.py` | Writes CLI results to CSV and JSON |
| `src/cli.py` | Provides the command-line entry point |

## Transaction Data Model

Each transaction contains:

| Field | Description | Example |
|---|---|---|
| `date` | Date shown on the statement | `12/05/2026` |
| `iso_date` | Standardised ISO date | `2026-05-12` |
| `description` | Transaction description | `CARD PAYMENT TO EXAMPLE STORE` |
| `amount` | Signed transaction amount | `-125.50` |
| `currency` | Statement currency | `GBP` |

Example:

```json
{
  "date": "12/05/2026",
  "iso_date": "2026-05-12",
  "description": "CARD PAYMENT TO EXAMPLE STORE",
  "amount": -125.50,
  "currency": "GBP"
}
```

## Design Decisions

### Why Use OCR Before Gemini?

Bank statement PDFs may contain:

- scanned images;
- embedded text;
- multi-column layouts;
- tables;
- inconsistent formatting.

docTR provides a consistent text extraction step before the content is passed to Gemini.

### Why Use Gemini?

Bank statement formats vary significantly across banks.

Instead of building a separate parser for every format, Gemini interprets the extracted text and returns a consistent structured schema.

### Why Keep Manual Review?

OCR and LLM outputs may contain errors.

The interface therefore supports a human-in-the-loop workflow where extracted transactions are reviewed before export.

This is particularly important when the output is used for financial analysis, audit testing or exception review.

### Why Use Signed Amounts?

Signed amounts provide a consistent transaction rule:

```text
negative = debit
positive = credit
```

This simplifies filtering and avoids relying only on inconsistent words such as `debit`, `credit`, `paid in` or `paid out`.

## Limitations

- Extraction quality depends on the readability and layout of the source PDF.
- Handwritten statements are not currently supported.
- Password-protected PDFs must be unlocked before upload.
- Gemini may occasionally misclassify transactions or transaction signs.
- Date formats may require additional validation for unusual statement layouts.
- Live FX conversion depends on the availability of the Frankfurter API.
- The application currently focuses on debit transaction review.
- Sensitive financial documents should not be processed without considering data privacy requirements.
- The project is a prototype and should not be treated as a substitute for professional review.

## Security and Privacy

Bank statements can contain confidential financial and personal information.

Before using the application with real documents:

- review the data handling terms of the selected LLM provider;
- avoid committing bank statements or extracted outputs to GitHub;
- keep API keys in environment variables;
- exclude uploaded files and generated outputs through `.gitignore`;
- use anonymised or synthetic statements for demonstrations;
- remove account numbers, names and addresses from screenshots.

Recommended `.gitignore` entries:

```gitignore
.env
uploads/
output/
samples/private/
*.pdf
*.xlsx
*.csv
*.json
```

Only include synthetic example files that are safe to publish.

## Potential Improvements

- Add confidence scores for extracted transactions.
- Display the source PDF alongside the review table.
- Link each extracted transaction to its source page.
- Use OCR bounding boxes to highlight the original transaction.
- Add duplicate transaction detection.
- Support credit transaction review.
- Add reconciliation between opening balance, movements and closing balance.
- Add bank-specific extraction validation.
- Add asynchronous processing for large documents.
- Add user authentication and encrypted file storage.
- Containerise the application with Docker.
- Deploy the web interface to a cloud environment.
- Add automated tests for extraction, filtering and export logic.
- Add an audit trail recording manual selection changes.

## Example Use Cases

- Audit sample selection
- Expense review
- High-value payment identification
- Transaction exception analysis
- Bank statement digitisation
- Financial data preparation
- Account reconciliation support
- Batch extraction of statement transactions

## Disclaimer

This project is intended for demonstration and educational purposes.

Extracted transactions should always be reviewed against the original bank statement before being used for audit, accounting, compliance or financial decision-making.



