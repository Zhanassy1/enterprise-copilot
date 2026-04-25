"""Unit tests for maintenance Celery tasks (purge, immediate hard delete)."""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.celery_app import celery_app
from app.tasks.maintenance import (
    delete_document_blob_and_row,
    hard_delete_soft_deleted_document_task,
    process_usage_outbox_task,
    requeue_stale_ingestion_jobs_task,
)


class MaintenanceTaskTests(unittest.TestCase):
    def test_beat_schedule_registers_purge(self) -> None:
        bs = celery_app.conf.beat_schedule or {}
        self.assertIn("purge-soft-deleted-documents-daily", bs)
        entry = bs["purge-soft-deleted-documents-daily"]
        self.assertEqual(entry["task"], "maintenance.purge_soft_deleted_documents")
        self.assertIn("schedule", entry)

    def test_beat_schedule_registers_usage_outbox(self) -> None:
        bs = celery_app.conf.beat_schedule or {}
        self.assertIn("process-usage-outbox-minutely", bs)
        self.assertEqual(bs["process-usage-outbox-minutely"]["task"], "maintenance.process_usage_outbox")

    def test_beat_schedule_registers_stale_ingestion_requeue(self) -> None:
        bs = celery_app.conf.beat_schedule or {}
        self.assertIn("requeue-stale-ingestion-every-5m", bs)
        self.assertEqual(
            bs["requeue-stale-ingestion-every-5m"]["task"],
            "maintenance.requeue_stale_ingestion_jobs",
        )

    def test_delete_document_blob_and_row(self) -> None:
        storage = MagicMock()
        db = MagicMock()
        doc = MagicMock()
        doc.storage_key = "uploads/x/y.bin"
        delete_document_blob_and_row(db, doc, storage)
        storage.delete.assert_called_once_with("uploads/x/y.bin")
        db.delete.assert_called_once_with(doc)

    @patch("app.tasks.maintenance.get_storage_service")
    @patch("app.tasks.maintenance.SessionLocal")
    def test_hard_delete_soft_deleted_document_ok(self, session_local: MagicMock, get_storage: MagicMock) -> None:
        ws_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        doc = MagicMock()
        doc.id = doc_id
        doc.workspace_id = ws_id
        doc.deleted_at = datetime.now(UTC)
        doc.storage_key = "k"

        db = MagicMock()
        db.scalar.return_value = doc
        session_local.return_value = db
        get_storage.return_value = MagicMock()

        out = hard_delete_soft_deleted_document_task(document_id=str(doc_id), workspace_id=str(ws_id))
        self.assertEqual(out["status"], "ok")
        get_storage.return_value.delete.assert_called_once_with("k")
        db.delete.assert_called_once_with(doc)
        db.commit.assert_called_once()

    @patch("app.tasks.maintenance.get_storage_service")
    @patch("app.tasks.maintenance.SessionLocal")
    def test_hard_delete_ignores_not_soft_deleted(self, session_local: MagicMock, get_storage: MagicMock) -> None:
        ws_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        doc = MagicMock()
        doc.workspace_id = ws_id
        doc.deleted_at = None

        db = MagicMock()
        db.scalar.return_value = doc
        session_local.return_value = db

        out = hard_delete_soft_deleted_document_task(document_id=str(doc_id), workspace_id=str(ws_id))
        self.assertEqual(out["reason"], "not_soft_deleted")
        get_storage.return_value.delete.assert_not_called()

    @patch("app.tasks.maintenance.process_usage_outbox_batch")
    @patch("app.tasks.maintenance.SessionLocal")
    def test_process_usage_outbox_task_calls_batch(self, session_local: MagicMock, batch: MagicMock) -> None:
        db = MagicMock()
        session_local.return_value = db
        batch.return_value = {"processed": 3, "claimed": 3, "oldest_pending_age_seconds": None}

        out = process_usage_outbox_task(limit=10)

        self.assertEqual(out["processed"], 3)
        batch.assert_called_once_with(db, limit=10)
        db.close.assert_called_once()

    @patch("app.tasks.maintenance.requeue_stale_ingestion_jobs")
    @patch("app.tasks.maintenance.SessionLocal")
    def test_requeue_stale_ingestion_jobs_task(
        self, session_local: MagicMock, requeue_fn: MagicMock
    ) -> None:
        jid = uuid.uuid4()
        requeue_fn.return_value = MagicMock(requeued=1, job_ids=[jid])
        db = MagicMock()
        session_local.return_value = db

        out = requeue_stale_ingestion_jobs_task(limit=7)

        self.assertEqual(out["requeued"], 1)
        self.assertEqual(out["job_ids"], [str(jid)])
        requeue_fn.assert_called_once_with(db, limit=7)
        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
