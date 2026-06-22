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
    # Imported lazily so importing this module doesn't pull in torch/doctr
    # unless OCR is actually run.
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor

    doc = DocumentFile.from_pdf(pdf_path)
    model = ocr_predictor(pretrained=True)  # detection + recognition pipeline
    return model(doc)  # a docTR Document: pages -> blocks -> lines -> words


def result_to_text(result, min_confidence: float = MIN_CONFIDENCE) -> str:
    # Flatten the page/block/line/word tree into plain text, one line per
    # detected text line, dropping any word docTR wasn't confident about.
    lines_out = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                words = [w.value for w in line.words if w.confidence >= min_confidence]
                if words:
                    lines_out.append(" ".join(words))
    return "\n".join(lines_out)


def result_to_words(result, min_confidence: float = MIN_CONFIDENCE) -> list[list[dict]]:
    """Per-page recognised words with pixel bounding boxes (x0/x1/top/bottom).

    Coordinates are in pixels of the page image docTR ran OCR on (see
    each page's "width"/"height" in the returned structure), matching
    the box format used by extract.extract_words_per_page.
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
