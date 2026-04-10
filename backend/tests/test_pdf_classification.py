"""Unit tests for PDF native-text classification heuristics."""

import unittest

from app.constants.pdf_ingestion import PDF_KIND_MIXED, PDF_KIND_SCANNED, PDF_KIND_TEXT_NATIVE
from app.services.pdf_classification import classify_pdf_pages, needs_ocr


class PdfClassificationTests(unittest.TestCase):
    def test_empty_pages_is_scanned(self) -> None:
        s = classify_pdf_pages([], min_chars_per_page=20, min_mean=50, max_empty_ratio=0.35)
        self.assertEqual(s.pdf_kind, PDF_KIND_SCANNED)
        self.assertTrue(needs_ocr(s))

    def test_dense_text_is_native(self) -> None:
        s = classify_pdf_pages([200, 200, 200], min_chars_per_page=20, min_mean=50, max_empty_ratio=0.35)
        self.assertEqual(s.pdf_kind, PDF_KIND_TEXT_NATIVE)
        self.assertFalse(needs_ocr(s))

    def test_all_tiny_pages_is_scanned(self) -> None:
        s = classify_pdf_pages([2, 2, 2, 2], min_chars_per_page=20, min_mean=50, max_empty_ratio=0.35)
        self.assertEqual(s.pdf_kind, PDF_KIND_SCANNED)
        self.assertTrue(needs_ocr(s))

    def test_partial_pages_is_mixed(self) -> None:
        s = classify_pdf_pages([200, 2, 2, 200], min_chars_per_page=20, min_mean=50, max_empty_ratio=0.35)
        self.assertEqual(s.pdf_kind, PDF_KIND_MIXED)
        self.assertTrue(needs_ocr(s))


if __name__ == "__main__":
    unittest.main()
