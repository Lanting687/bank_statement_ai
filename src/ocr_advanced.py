"""Advanced OCR text extraction using docTR (deep-learning document OCR).

Takes a PDF path, runs OCR over every page, and writes only the
recognised words (confidence >= --min-confidence) to a .txt file in
reading order. Optionally also writes per-word bounding boxes as JSON
so downstream code can reconstruct columns/tables instead of relying
on flattened reading order.
"""
from __future__ import annotations

import argparse
import json
import os

MIN_CONFIDENCE = 0.5  # drop words the model isn't confident about


def run_ocr(pdf_path: str):
    """
    These imports are placed inside the function, not at the top of the file.
    Reason: loading docTR and PyTorch takes several seconds and a lot of memory.
    If we imported them at the top, they would load every time the app starts —
    even when the user is just viewing the UI, dragging a PDF in, or changing
    filter settings. None of those actions need OCR.
    OCR is only needed when the user clicks the Process button, which is the
    only moment this function gets called. Keeping the imports here means
    docTR and PyTorch only load at that exact moment, keeping app startup fast.
    """
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor

    """
    Opens the PDF, screenshots each page into a pixel image (neural networks cannot
    read raw PDFs), and stores all page images together in doc for the neural network.
    """
    doc = DocumentFile.from_pdf(pdf_path)

    """
    Load two pre-trained neural networks packaged together:
      Network 1 (Detection)   — scans the image and finds where the text is (draws boxes)
      Network 2 (Recognition) — reads what the text says inside each box
    pretrained=True means we use weights already trained by docTR — no training needed on our end.
    """
    model = ocr_predictor(pretrained=True)

    """
    Run both networks on the page images and return the result tree
    (Document -> pages -> blocks -> lines -> words) back to pipeline.py.
    """
    return model(doc)


def result_to_text(result, min_confidence: float = MIN_CONFIDENCE) -> str:
    """
    Receives the Document tree from pipeline.py, flattens it into a plain text string
    (one line per text line, low-confidence words dropped), and returns it to Gemini.
    -> str means this function always returns a string.
    """
    lines_out = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                words = [w.value for w in line.words if w.confidence >= min_confidence]
                if words:
                    lines_out.append(" ".join(words))
    """
    \n is a newline — puts each transaction on its own line so Gemini can
    tell where one transaction ends and the next begins.
    """
    return "\n".join(lines_out)


def result_to_words(result, min_confidence: float = MIN_CONFIDENCE) -> list[list[dict]]:
    """
    Returns the position of every word on the page as pixel coordinates (x0, x1, top, bottom).
    Plain text from result_to_text() loses position info — this function keeps it.
    Useful for complex bank statement layouts where amounts and labels sit in separate
    columns, and knowing the x-coordinate tells you which column a word belongs to.
    Not used in the normal pipeline — only called via CLI with --bbox-json for inspection.
    """
    pages_out = []
    for page in result.pages:
        height, width = page.dimensions
        words = []
        for block in page.blocks:
            for line in block.lines:
                for w in line.words:
                    if w.confidence < min_confidence:
                        continue
                    # docTR geometry is relative (0-1); scale to pixel coords.
                    (x0, y0), (x1, y1) = w.geometry
                    words.append({
                        "text": w.value,
                        "x0": x0 * width,
                        "x1": x1 * width,
                        "top": y0 * height,
                        "bottom": y1 * height,
                        "confidence": w.confidence,
                    })
        pages_out.append({"width": width, "height": height, "words": words})
    return pages_out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--min-confidence", type=float, default=MIN_CONFIDENCE,
        help=f"Minimum word confidence to keep, 0-1 (default: {MIN_CONFIDENCE})",
    )
    parser.add_argument(
        "--out", default=None,
        help="Output txt path (default: <pdf_basename>_doctr.txt)",
    )
    parser.add_argument(
        "--bbox-json", nargs="?", const="", default=None,
        help="Also write per-word bounding boxes as JSON "
             "(default path: <pdf_basename>_doctr_words.json)",
    )
    args = parser.parse_args()

    base = os.path.splitext(os.path.basename(args.pdf_path))[0]
    out_path = args.out or f"{base}_doctr.txt"

    # Run OCR once; both outputs below are derived from the same result.
    result = run_ocr(args.pdf_path)

    text = result_to_text(result, args.min_confidence)
    with open(out_path, "w") as f:
        f.write(text)
    print(f"Wrote {out_path} ({len(text)} chars)")

    # --bbox-json is opt-in: most callers (e.g. the main pipeline) only need text.
    if args.bbox_json is not None:
        bbox_path = args.bbox_json or f"{base}_doctr_words.json"
        pages = result_to_words(result, args.min_confidence)
        with open(bbox_path, "w") as f:
            json.dump(pages, f, indent=2)
        total_words = sum(len(p["words"]) for p in pages)
        print(f"Wrote {bbox_path} ({total_words} words across {len(pages)} pages)")


if __name__ == "__main__":
    main()
