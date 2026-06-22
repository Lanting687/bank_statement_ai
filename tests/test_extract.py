from src import extract


def _raise_if_called(pdf_path):
    raise AssertionError("should not have been called")


def test_uses_direct_text_when_pages_have_enough_chars(monkeypatch):
    monkeypatch.setattr(extract, "_extract_text_direct", lambda pdf_path: ["a" * 50, "b" * 50])
    monkeypatch.setattr(extract, "_extract_text_ocr", _raise_if_called)
    assert extract.extract_text("statement.pdf") == ("a" * 50) + "\n" + ("b" * 50)


def test_falls_back_to_ocr_when_direct_text_is_sparse(monkeypatch):
    monkeypatch.setattr(extract, "_extract_text_direct", lambda pdf_path: ["", ""])
    monkeypatch.setattr(extract, "_extract_text_ocr", lambda pdf_path: "OCR RESULT")
    assert extract.extract_text("statement.pdf") == "OCR RESULT"


def test_falls_back_to_ocr_when_pdf_has_no_pages(monkeypatch):
    monkeypatch.setattr(extract, "_extract_text_direct", lambda pdf_path: [])
    monkeypatch.setattr(extract, "_extract_text_ocr", lambda pdf_path: "OCR RESULT")
    assert extract.extract_text("statement.pdf") == "OCR RESULT"


def test_falls_back_to_ocr_right_below_the_chars_per_page_threshold(monkeypatch):
    short_page = "x" * (extract.MIN_CHARS_PER_PAGE - 1)
    monkeypatch.setattr(extract, "_extract_text_direct", lambda pdf_path: [short_page])
    monkeypatch.setattr(extract, "_extract_text_ocr", lambda pdf_path: "OCR RESULT")
    assert extract.extract_text("statement.pdf") == "OCR RESULT"


def test_uses_direct_text_right_at_the_chars_per_page_threshold(monkeypatch):
    page = "x" * extract.MIN_CHARS_PER_PAGE
    monkeypatch.setattr(extract, "_extract_text_direct", lambda pdf_path: [page])
    monkeypatch.setattr(extract, "_extract_text_ocr", _raise_if_called)
    assert extract.extract_text("statement.pdf") == page
