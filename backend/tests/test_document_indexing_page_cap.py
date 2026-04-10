"""Worker path: page count vs plan cap (enforcement in DocumentIndexingService.run)."""

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.document_indexing import DocumentIndexingService
from app.services.pdf_ingestion import PdfIndexingExtractResult
from app.services.text_extraction import ExtractedDocument


class DocumentIndexingPageCapTests(unittest.TestCase):
    def test_raises_when_pages_exceed_plan_limit(self) -> None:
        mock_db = MagicMock()
        storage = MagicMock()
        storage.local_path.return_value.__enter__.return_value = MagicMock()
        storage.local_path.return_value.__exit__.return_value = None

        doc = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            storage_key="k",
            content_type="application/pdf",
            filename="x.pdf",
            status="queued",
            extracted_text=None,
            page_count=None,
            language=None,
            error_message=None,
            indexed_at=None,
            parser_version=None,
        )
        pdf_stub = PdfIndexingExtractResult(
            extracted=ExtractedDocument(text="a\fb", page_count=999, language="en"),
            pdf_kind="text_native",
            ocr_applied=False,
            parser_version="v2",
            extraction_meta={},
        )

        with (
            patch("app.services.document_indexing.extract_pdf_for_indexing", return_value=pdf_stub),
            patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=10),
            patch(
                "app.services.document_indexing.chunk_text",
                side_effect=AssertionError("chunk_text must not run when page cap exceeded"),
            ),
        ):
            svc = DocumentIndexingService(mock_db, storage)
            with self.assertRaises(ValueError) as err:
                svc.run(doc)  # type: ignore[arg-type]
            self.assertIn("page limit", str(err.exception).lower())


if __name__ == "__main__":
    unittest.main()
