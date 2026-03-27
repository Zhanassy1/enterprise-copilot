import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.tasks.ingestion import ingest_document_task


class _FakeDb:
    def __init__(self, scalars):
        self._scalars = list(scalars)
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, _query):
        if not self._scalars:
            return None
        return self._scalars.pop(0)

    def add(self, _obj) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        return None


class IngestionTaskUnitTests(unittest.TestCase):
    def _job_and_doc(self, attempts: int = 0):
        workspace_id = uuid.uuid4()
        document_id = uuid.uuid4()
        dedup_key = f"{workspace_id}:{document_id}"
        job = SimpleNamespace(
            id=uuid.uuid4(),
            document_id=document_id,
            workspace_id=workspace_id,
            deduplication_key=dedup_key,
            status="queued",
            attempts=attempts,
            error_message=None,
            locked_at=None,
            completed_at=None,
            retry_after_seconds=None,
            dead_lettered_at=None,
            celery_task_id=None,
            last_retry_at=None,
            available_at=None,
        )
        doc = SimpleNamespace(
            id=document_id,
            workspace_id=workspace_id,
            status="queued",
            error_message=None,
        )
        return job, doc, dedup_key

    def test_retries_when_attempts_left(self) -> None:
        job, doc, dedup_key = self._job_and_doc(attempts=0)
        fake_db = _FakeDb([job, doc, job, doc])

        retry_error = RuntimeError("retry-called")
        ingest_document_task.push_request(id="task-123")
        try:
            with (
                patch.object(ingest_document_task, "retry", Mock(side_effect=retry_error)),
                patch("app.tasks.ingestion.SessionLocal", return_value=fake_db),
                patch("app.tasks.ingestion.settings.ingestion_max_attempts", 3),
                patch("app.tasks.ingestion.DocumentIndexingService") as indexer_cls,
            ):
                indexer_cls.return_value.run.side_effect = RuntimeError("boom")
                with self.assertRaises(RuntimeError) as err:
                    ingest_document_task.run(
                        document_id=str(doc.id),
                        workspace_id=str(doc.workspace_id),
                        ingestion_job_id=str(job.id),
                        deduplication_key=dedup_key,
                    )
                self.assertEqual(str(err.exception), "retry-called")
                self.assertEqual(job.status, "retrying")
                self.assertEqual(doc.status, "retrying")
                self.assertEqual(job.attempts, 1)
                self.assertGreaterEqual(fake_db.commits, 1)
        finally:
            ingest_document_task.pop_request()

    def test_marks_failed_when_attempts_exhausted(self) -> None:
        job, doc, dedup_key = self._job_and_doc(attempts=2)
        fake_db = _FakeDb([job, doc, job, doc])
        ingest_document_task.push_request(id="task-456")
        try:
            with (
                patch("app.tasks.ingestion.SessionLocal", return_value=fake_db),
                patch("app.tasks.ingestion.settings.ingestion_max_attempts", 3),
                patch("app.tasks.ingestion.DocumentIndexingService") as indexer_cls,
            ):
                indexer_cls.return_value.run.side_effect = RuntimeError("fatal")
                out = ingest_document_task.run(
                    document_id=str(doc.id),
                    workspace_id=str(doc.workspace_id),
                    ingestion_job_id=str(job.id),
                    deduplication_key=dedup_key,
                )
                self.assertEqual(out["status"], "failed")
                self.assertEqual(job.status, "failed")
                self.assertEqual(doc.status, "failed")
                self.assertEqual(job.attempts, 3)
                self.assertGreaterEqual(fake_db.commits, 1)
        finally:
            ingest_document_task.pop_request()


if __name__ == "__main__":
    unittest.main()
