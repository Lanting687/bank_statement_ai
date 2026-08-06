"""Tests for the page-level OCR data model and its use in ocr_advanced.py.

These use small fake docTR-shaped objects (Document -> pages -> blocks ->
lines -> words) rather than running real OCR, so no docTR/PyTorch model
load and no network access is required.
"""
from src.models import OCRPage, OCRResult
from src.ocr_advanced import result_to_ocr_result, result_to_text


class _Word:
    def __init__(self, value: str, confidence: float = 1.0):
        self.value = value
        self.confidence = confidence


class _Line:
    def __init__(self, words):
        self.words = words


class _Block:
    def __init__(self, lines):
        self.lines = lines


class _Page:
    def __init__(self, blocks):
        self.blocks = blocks


class _Document:
    def __init__(self, pages):
        self.pages = pages


# --- OCRResult / OCRPage ---

def test_full_text_combines_pages_in_order():
    result = OCRResult(pages=(
        OCRPage(page_number=1, text="line one\nline two"),
        OCRPage(page_number=2, text="line three"),
    ))
    assert result.full_text == "line one\nline two\nline three"


def test_full_text_skips_empty_pages_without_blank_lines():
    # A page with no recognised text should not introduce a stray blank line.
    result = OCRResult(pages=(
        OCRPage(page_number=1, text="line one"),
        OCRPage(page_number=2, text=""),
        OCRPage(page_number=3, text="line two"),
    ))
    assert result.full_text == "line one\nline two"


def test_full_text_empty_when_no_pages_have_text():
    result = OCRResult(pages=(OCRPage(page_number=1, text=""),))
    assert result.full_text == ""


def test_page_count():
    result = OCRResult(pages=(OCRPage(1, "a"), OCRPage(2, "b"), OCRPage(3, "c")))
    assert result.page_count == 3


def test_page_lookup_by_number():
    result = OCRResult(pages=(OCRPage(1, "a"), OCRPage(2, "b")))
    assert result.page(2).text == "b"


def test_page_lookup_out_of_range_returns_none():
    result = OCRResult(pages=(OCRPage(1, "a"),))
    assert result.page(5) is None


# --- result_to_ocr_result / result_to_text (built from fake docTR trees) ---

def test_result_to_ocr_result_preserves_page_order_and_numbering():
    doc = _Document(pages=[
        _Page(blocks=[_Block(lines=[_Line(words=[_Word("Hello"), _Word("world")])])]),
        _Page(blocks=[_Block(lines=[_Line(words=[_Word("Second"), _Word("page")])])]),
    ])
    result = result_to_ocr_result(doc)
    assert [p.page_number for p in result.pages] == [1, 2]
    assert result.pages[0].text == "Hello world"
    assert result.pages[1].text == "Second page"


def test_result_to_ocr_result_drops_low_confidence_words():
    doc = _Document(pages=[
        _Page(blocks=[_Block(lines=[
            _Line(words=[_Word("keep", confidence=0.9), _Word("drop", confidence=0.1)]),
        ])]),
    ])
    result = result_to_ocr_result(doc, min_confidence=0.5)
    assert result.pages[0].text == "keep"


def test_result_to_ocr_result_multiple_lines_per_page():
    doc = _Document(pages=[
        _Page(blocks=[_Block(lines=[
            _Line(words=[_Word("line1")]),
            _Line(words=[_Word("line2")]),
        ])]),
    ])
    result = result_to_ocr_result(doc)
    assert result.pages[0].text == "line1\nline2"


def test_result_to_ocr_result_empty_page_yields_empty_text():
    doc = _Document(pages=[_Page(blocks=[])])
    result = result_to_ocr_result(doc)
    assert result.pages[0].text == ""


def test_result_to_text_matches_full_text_for_same_document():
    # result_to_text is the backward-compatible single-string view; it must
    # keep returning exactly what callers (the CLI) got before this refactor.
    doc = _Document(pages=[
        _Page(blocks=[_Block(lines=[_Line(words=[_Word("A")])])]),
        _Page(blocks=[_Block(lines=[_Line(words=[_Word("B")])])]),
    ])
    assert result_to_text(doc) == result_to_ocr_result(doc).full_text == "A\nB"
