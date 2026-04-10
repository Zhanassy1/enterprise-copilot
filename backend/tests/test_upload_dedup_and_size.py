"""Upload deduplication (in-flight statuses) and early max-size handling."""

import io
import tempfile
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.upload_limits import MAX_UPLOAD_BYTES, UploadTooLargeError
from app.services.document_ingestion import (
    DocumentIngestionService,
    _is_documents_workspace_sha256_unique_violation,
)


class UploadDedupAndSizeTests(unittest.TestCase):
    def test_duplicate_queued_returns_existing_and_deletes_new_blob(self) -> None:
        mock_db = MagicMock()
        user_id = uuid.uuid4()
        existing = SimpleNamespace(
            id=uuid.uuid4(),
            filename="old.txt",
            status="queued",
            workspace_id=uuid.uuid4(),
            content_type="text/plain",
            error_message=None,
            file_size_bytes=10,
            sha256="b" * 64,
            page_count=None,
            language=None,
            parser_version=None,
            indexed_at=None,
            created_at=datetime.now(UTC),
            owner_id=user_id,
        )
        mock_db.scalar.side_effect = [existing]
        storage = MagicMock()
        stored = SimpleNamespace(storage_key="new-key", size_bytes=10, sha256="b" * 64)
        storage.save_upload.return_value = stored
        storage.delete = MagicMock()
        storage.local_path.return_value.__enter__.return_value = __file__
        storage.local_path.return_value.__exit__.return_value = None

        workspace = SimpleNamespace(id=uuid.uuid4())
        file = UploadFile(filename="x.txt", file=io.BytesIO(b"hello"), headers={"content-type": "text/plain"})

        with patch("app.services.document_ingestion.scan_uploaded_file_safe"):
            svc = DocumentIngestionService(mock_db, storage)
            out = svc.upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(out.chunks_created, 0)
        self.assertEqual(out.document.id, existing.id)
        storage.delete.assert_called_once_with("new-key")
        mock_db.commit.assert_not_called()

    def test_upload_413_when_storage_raises_upload_too_large(self) -> None:
        mock_db = MagicMock()
        storage = MagicMock()
        storage.save_upload.side_effect = UploadTooLargeError()

        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="x.txt", file=io.BytesIO(b"x"), headers={"content-type": "text/plain"})

        with (
            patch("app.services.document_ingestion.scan_uploaded_file_safe") as scan,
            patch("app.services.document_ingestion.validate_upload"),
        ):
            svc = DocumentIngestionService(mock_db, storage)
            with self.assertRaises(HTTPException) as ctx:
                svc.upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(ctx.exception.status_code, 413)
        scan.assert_not_called()
        mock_db.execute.assert_not_called()


class UniqueViolationHelperTests(unittest.TestCase):
    def test_detects_partial_index_name_in_message(self) -> None:
        exc = IntegrityError(
            "duplicate key value violates unique constraint uq_documents_workspace_sha256_active",
            None,
            None,
        )
        self.assertTrue(_is_documents_workspace_sha256_unique_violation(exc))


class LocalStorageEarlySizeTests(unittest.TestCase):
    def test_local_save_aborts_over_max_without_full_read(self) -> None:
        from app.services.storage.local import LocalStorageService

        with tempfile.TemporaryDirectory() as d:
            svc = LocalStorageService(upload_dir=d)
            oversized = io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1))
            with self.assertRaises(UploadTooLargeError):
                svc.save_upload(oversized, "huge.txt")
            self.assertEqual(list(Path(d).glob("*")), [])


if __name__ == "__main__":
    unittest.main()
