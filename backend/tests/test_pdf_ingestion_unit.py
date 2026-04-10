"""pdf_ingestion orchestration with mocks (no AWS)."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.constants.pdf_ingestion import PDF_KIND_SCANNED, PDF_KIND_TEXT_NATIVE
from app.services.pdf_classification import PdfPageTextStats
from app.services.pdf_ingestion import extract_pdf_for_indexing


def _ingestion_settings_stub(**overrides):
    base = dict(
        pdf_ocr_enabled=False,
        pdf_ocr_provider="none",
        pdf_min_chars_per_page=20,
        pdf_min_mean_chars_per_page=50,
        pdf_max_empty_page_ratio=0.35,
        pdf_ocr_staging_bucket="",
        pdf_ocr_staging_prefix="ocr-staging",
        textract_max_wait_seconds=300.0,
        textract_poll_interval_seconds=1.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class PdfIngestionUnitTests(unittest.TestCase):
    @patch("app.services.pdf_ingestion.run_textract_document_text_detection")
    @patch("app.services.pdf_ingestion.read_pdf_native_text_and_stats")
    def test_textract_when_weak_native_and_enabled(
        self, mock_native: MagicMock, mock_tx: MagicMock
    ) -> None:
        weak = PdfPageTextStats(
            page_chars=[0, 0],
            total_chars=0,
            page_count=2,
            empty_pages=2,
            mean_chars_per_page=0.0,
            empty_page_ratio=1.0,
            pdf_kind=PDF_KIND_SCANNED,
            sufficient_native_text=False,
        )
        mock_native.return_value = ("", weak)
        mock_tx.return_value = MagicMock(text="Hello from OCR", page_count=2, job_id="job-1")

        stub = _ingestion_settings_stub(
            pdf_ocr_enabled=True,
            pdf_ocr_provider="textract",
            pdf_ocr_staging_bucket="staging",
        )
        with patch("app.services.pdf_ingestion.settings", stub):
            out = extract_pdf_for_indexing("/tmp/x.pdf", storage_key="s3://b/k.pdf")

        mock_tx.assert_called_once_with(bucket="b", key="k.pdf")
        self.assertTrue(out.ocr_applied)
        self.assertEqual(out.extracted.text, "Hello from OCR")
        self.assertEqual(out.parser_version, "v2+textract")
        self.assertEqual(out.extraction_meta.get("ocr_provider"), "textract")

    @patch("app.services.pdf_ingestion.read_pdf_native_text_and_stats")
    def test_no_ocr_when_strong_native(self, mock_native: MagicMock) -> None:
        strong = PdfPageTextStats(
            page_chars=[500],
            total_chars=500,
            page_count=1,
            empty_pages=0,
            mean_chars_per_page=500.0,
            empty_page_ratio=0.0,
            pdf_kind=PDF_KIND_TEXT_NATIVE,
            sufficient_native_text=True,
        )
        mock_native.return_value = ("full text here", strong)

        stub = _ingestion_settings_stub(pdf_ocr_enabled=True, pdf_ocr_provider="textract")
        with patch("app.services.pdf_ingestion.settings", stub):
            out = extract_pdf_for_indexing("/tmp/x.pdf", storage_key="s3://b/k.pdf")

        self.assertFalse(out.ocr_applied)
        self.assertEqual(out.extracted.text, "full text here")
        self.assertEqual(out.parser_version, "v2")


if __name__ == "__main__":
    unittest.main()
