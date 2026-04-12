"""Enqueue immediate hard-delete after soft-delete when flag is enabled."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock, patch

from app.services.document_ingestion import DocumentIngestionService


class DeleteDocumentImmediateTests(unittest.TestCase):
    @patch("app.tasks.maintenance.hard_delete_soft_deleted_document_task")
    def test_enqueues_hard_delete_when_immediate_flag_on(self, task_mock: MagicMock) -> None:
        ws_id = uuid.uuid4()
        doc = MagicMock()
        doc.workspace_id = ws_id
        doc.id = uuid.uuid4()

        db = MagicMock()
        storage = MagicMock()
        svc = DocumentIngestionService(db, storage)

        with patch("app.services.document_ingestion.settings.immediate_hard_delete_after_soft_delete", True):
            svc.delete_document(doc, ws_id)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        task_mock.apply_async.assert_called_once()
        kwargs = task_mock.apply_async.call_args.kwargs["kwargs"]
        self.assertEqual(kwargs["document_id"], str(doc.id))
        self.assertEqual(kwargs["workspace_id"], str(ws_id))

    def test_does_not_enqueue_when_flag_off(self) -> None:
        ws_id = uuid.uuid4()
        doc = MagicMock()
        doc.workspace_id = ws_id
        doc.id = uuid.uuid4()

        db = MagicMock()
        storage = MagicMock()
        svc = DocumentIngestionService(db, storage)

        with patch("app.tasks.maintenance.hard_delete_soft_deleted_document_task") as task_mock:
            with patch("app.services.document_ingestion.settings.immediate_hard_delete_after_soft_delete", False):
                svc.delete_document(doc, ws_id)
            task_mock.apply_async.assert_not_called()


if __name__ == "__main__":
    unittest.main()
