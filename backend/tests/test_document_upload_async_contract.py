import io
import os
import unittest
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from app.models.document import Document, IngestionJob
from app.services import document_ingestion as document_ingestion_module
from app.services.document_ingestion import DocumentIngestionService


class _StoredUpload:
    def __init__(self) -> None:
        self.storage_key = "uploads/test-contract.txt"
        self.size_bytes = 32
        self.sha256 = "a" * 64


class _FakeStorage:
    def save_upload(self, _file_obj, _name: str) -> _StoredUpload:
        return _StoredUpload()

    def delete(self, _storage_key: str) -> None:
        return None

    @contextmanager
    def local_path(self, _storage_key: str):
        yield __file__


class _FakeDb:
    def __init__(self) -> None:
        self._objects = []

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._objects.append(obj)

    def flush(self) -> None:
        return None

    def execute(self, *_args, **_kwargs):
        return None

    def scalar(self, _query):
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, obj) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    def get(self, entity, id_):
        for obj in self._objects:
            if isinstance(obj, entity) and getattr(obj, "id", None) == id_:
                return obj
        return None


class _SequenceTrackingDb(_FakeDb):
    """Tracks commit vs record_event ordering for async upload contract."""

    def __init__(self) -> None:
        super().__init__()
        self.sequence: list[str] = []

    def commit(self) -> None:
        self.sequence.append("commit")


class DocumentUploadAsyncContractTests(unittest.TestCase):
    def test_async_upload_enqueues_task_and_returns_queued_document(self) -> None:
        db = _FakeDb()
        service = DocumentIngestionService(db, _FakeStorage())
        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="contract.txt", file=io.BytesIO(b"contract body"), headers={"content-type": "text/plain"})

        with (
            patch.dict(os.environ, {"INGESTION_ASYNC_ENABLED": "1"}, clear=False),
            patch("app.services.document_ingestion.settings.ingestion_async_enabled", True),
            patch("app.services.document_ingestion.ingest_document_task.apply_async") as publish_mock,
        ):
            result = service.upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(result.document.status, "queued")
        self.assertEqual(result.chunks_created, 0)
        self.assertTrue(publish_mock.called)
        self.assertTrue(any(isinstance(obj, IngestionJob) for obj in db._objects))

    def test_async_upload_pre_enqueue_commit_then_usage_events_then_final_commit(self) -> None:
        db = _SequenceTrackingDb()

        def record_side_effect(*_a, **_k):
            db.sequence.append("record")

        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="contract.txt", file=io.BytesIO(b"contract body"), headers={"content-type": "text/plain"})

        with (
            patch.dict(os.environ, {"INGESTION_ASYNC_ENABLED": "1"}, clear=False),
            patch("app.services.document_ingestion.settings.ingestion_async_enabled", True),
            patch("app.services.document_ingestion.ingest_document_task.apply_async"),
            patch("app.services.document_ingestion.record_event", side_effect=record_side_effect),
        ):
            DocumentIngestionService(db, _FakeStorage()).upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(db.sequence, ["commit", "record", "record", "commit"])

    def test_enqueue_failure_marks_doc_and_job_failed_no_usage_events(self) -> None:
        db = _FakeDb()
        record_calls: list[tuple[str, str]] = []

        def capture_record(_db, *, workspace_id, user_id, event_type, quantity, unit="count", metadata=None):
            record_calls.append((event_type, unit))
            return None

        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="contract.txt", file=io.BytesIO(b"contract body"), headers={"content-type": "text/plain"})

        with (
            patch.dict(os.environ, {"INGESTION_ASYNC_ENABLED": "1"}, clear=False),
            patch("app.services.document_ingestion.settings.ingestion_async_enabled", True),
            patch("app.services.document_ingestion.assert_quota"),
            patch("app.services.document_ingestion.scan_uploaded_file_safe"),
            patch("app.services.document_ingestion.ingest_document_task.apply_async", side_effect=RuntimeError("broker down")),
            patch("app.services.document_ingestion.record_event", side_effect=capture_record),
        ):
            with self.assertRaises(HTTPException) as ctx:
                DocumentIngestionService(db, _FakeStorage()).upload_document(user_id=user_id, workspace=workspace, file=file)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(record_calls, [])
        doc = next(o for o in db._objects if isinstance(o, Document))
        job = next(o for o in db._objects if isinstance(o, IngestionJob))
        self.assertEqual(doc.status, "failed")
        self.assertEqual(job.status, "failed")
        self.assertIn("enqueue", (doc.error_message or "").lower())

    def test_production_never_runs_sync_indexing_on_upload(self) -> None:
        """Defense in depth: `document_ingestion.py` rejects in-process indexing when ENVIRONMENT=production."""
        db = _FakeDb()
        service = DocumentIngestionService(db, _FakeStorage())
        workspace = SimpleNamespace(id=uuid.uuid4())
        user_id = uuid.uuid4()
        file = UploadFile(filename="contract.txt", file=io.BytesIO(b"contract body"), headers={"content-type": "text/plain"})

        with (
            patch("app.services.document_ingestion.settings.environment", "production"),
            patch("app.services.document_ingestion.settings.ingestion_async_enabled", False),
            patch("app.services.document_ingestion.settings.allow_sync_ingestion_for_dev", True),
            patch("app.services.document_ingestion.assert_quota"),
            patch("app.services.document_ingestion.record_event"),
            patch("app.services.document_ingestion.scan_uploaded_file_safe"),
        ):
            with self.assertRaises(HTTPException) as err:
                service.upload_document(user_id=user_id, workspace=workspace, file=file)
        self.assertEqual(err.exception.status_code, 503)
        self.assertIn("production", (err.exception.detail or "").lower())

    def test_effective_flags_read_env_when_integration_tests_and_settings_stale(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RUN_INTEGRATION_TESTS": "1",
                "INGESTION_ASYNC_ENABLED": "0",
                "ALLOW_SYNC_INGESTION_FOR_DEV": "1",
            },
            clear=False,
        ):
            with (
                patch.object(document_ingestion_module.settings, "ingestion_async_enabled", True),
                patch.object(document_ingestion_module.settings, "allow_sync_ingestion_for_dev", False),
                patch.object(document_ingestion_module.settings, "environment", "local"),
            ):
                async_on, allow_sync = document_ingestion_module._effective_ingestion_pipeline_flags()
        self.assertFalse(async_on)
        self.assertTrue(allow_sync)

    def test_effective_flags_skip_env_override_in_production(self) -> None:
        with patch.dict(
            os.environ,
            {"RUN_INTEGRATION_TESTS": "1", "ALLOW_SYNC_INGESTION_FOR_DEV": "1"},
            clear=False,
        ):
            with (
                patch.object(document_ingestion_module.settings, "ingestion_async_enabled", False),
                patch.object(document_ingestion_module.settings, "allow_sync_ingestion_for_dev", False),
                patch.object(document_ingestion_module.settings, "environment", "production"),
            ):
                async_on, allow_sync = document_ingestion_module._effective_ingestion_pipeline_flags()
        self.assertFalse(async_on)
        self.assertFalse(allow_sync)


if __name__ == "__main__":
    unittest.main()
