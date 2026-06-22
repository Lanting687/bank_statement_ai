"""CLI: bank statement PDF -> filtered payment transactions (CSV + JSON)."""
from __future__ import annotations

import argparse
from decimal import Decimal

from dotenv import load_dotenv

from .export import write_csv, write_json
from .filter import filter_payments
from .pipeline import extract_transactions


def main() -> None:
    # Load GEMINI_API_KEY (and any other secrets) from .env into the environment.
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the bank statement PDF")
    parser.add_argument(
        "--threshold", type=Decimal, required=True,
        help="Minimum payment (debit) amount to keep, e.g. 500",
    )
    parser.add_argument(
        "--out-prefix", default="transactions",
        help="Output file prefix; writes <prefix>.csv and <prefix>.json (default: transactions)",
    )
    args = parser.parse_args()

    # Full pipeline: docTR OCR -> Gemini structured extraction -> list[Transaction].
    transactions = extract_transactions(args.pdf_path)
    # Keep only debits whose absolute amount meets the threshold.
    payments = filter_payments(transactions, args.threshold)

    write_csv(payments, f"{args.out_prefix}.csv")
    write_json(payments, f"{args.out_prefix}.json")

    print(f"Parsed {len(transactions)} transactions, {len(payments)} payments >= {args.threshold}")
    print(f"Wrote {args.out_prefix}.csv and {args.out_prefix}.json")


if __name__ == "__main__":
    main()
