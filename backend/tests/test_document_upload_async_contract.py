import io
import uuid
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile

from app.models.document import IngestionJob
from app.services.document_ingestion import DocumentIngestionService


class _StoredUpload:
    def __init__(self) -> None:
        self.storage_path = "uploads/test-contract.txt"
        self.size_bytes = 32
        self.sha256 = "a" * 64


class _FakeStorage:
    def save_upload(self, _file_obj, _name: str) -> _StoredUpload:
        return _StoredUpload()

    def delete(self, _storage_path: str) -> None:
        return None


class _FakeDb:
    def __init__(self) -> None:
        self._objects = []

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            setattr(obj, "id", uuid.uuid4())
        self._objects.append(obj)

    def flush(self) -> None:
        return None

    def scalar(self, _query):
        return None

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)


class DocumentUploadAsyncContractTests(unittest.TestCase):
    def test_async_upload_enqueues_task_and_returns_queued_document(self) -> None:
        db = _FakeDb()
        service = DocumentIngestionService(db, _FakeStorage())
        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="contract.txt", file=io.BytesIO(b"contract body"), headers={"content-type": "text/plain"})

        with (
            patch("app.services.document_ingestion.settings.ingestion_async_enabled", True),
            patch("app.services.document_ingestion.ingest_document_task.apply_async") as publish_mock,
        ):
            result = service.upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(result.document.status, "queued")
        self.assertEqual(result.chunks_created, 0)
        self.assertTrue(publish_mock.called)
        self.assertTrue(any(isinstance(obj, IngestionJob) for obj in db._objects))


if __name__ == "__main__":
    unittest.main()
