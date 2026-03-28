"""Upload path calls assert_quota; 429 when quota enforcement raises."""

import io
import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile

from app.services.document_ingestion import DocumentIngestionService


class QuotaUploadBlocksTests(unittest.TestCase):
    def test_upload_raises_429_when_quota_blocks(self) -> None:
        """assert_quota in document_ingestion.upload_document (before document row commit)."""
        mock_db = MagicMock()
        mock_db.scalar.return_value = None
        storage = MagicMock()
        stored = SimpleNamespace(storage_key="k", size_bytes=100, sha256="a" * 64)
        storage.save_upload.return_value = stored
        storage.delete = MagicMock()
        storage.local_path.return_value.__enter__.return_value = __file__
        storage.local_path.return_value.__exit__.return_value = None

        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="x.txt", file=io.BytesIO(b"hello"), headers={"content-type": "text/plain"})

        with (
            patch("app.services.document_ingestion.scan_uploaded_file_safe"),
            patch(
                "app.services.document_ingestion.assert_quota",
                side_effect=HTTPException(status_code=429, detail="Workspace monthly upload quota exceeded"),
            ),
        ):
            svc = DocumentIngestionService(mock_db, storage)
            with self.assertRaises(HTTPException) as err:
                svc.upload_document(user_id=user_id, workspace=workspace, file=file)
        self.assertEqual(err.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
