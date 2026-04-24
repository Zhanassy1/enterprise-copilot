"""
Concurrent ingestion job claim (PostgreSQL FOR UPDATE SKIP LOCKED / UPDATE … RETURNING).

Run: RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_ingestion_job_claim_integration.py -v
"""

from __future__ import annotations

import os
import threading
import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.document import Document, IngestionJob
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.ingestion_job_claim import claim_job_for_celery
from app.services.workspace_service import ensure_default_roles


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class IngestionJobClaimIntegrationTests(unittest.TestCase):
    def _seed_queued_job(self) -> IngestionJob:
        db = SessionLocal()
        try:
            roles = ensure_default_roles(db)
            uid = uuid.uuid4()
            user = User(
                id=uid,
                email=f"claim_{uid.hex[:10]}@example.com",
                password_hash=hash_password("ClaimTest1!"),
                full_name="Claim Test",
            )
            db.add(user)
            db.flush()
            ws = Workspace(
                id=uuid.uuid4(),
                name="Claim WS",
                slug=f"claim-ws-{uuid.uuid4().hex[:10]}",
                owner_user_id=user.id,
                personal_for_user_id=user.id,
            )
            db.add(ws)
            db.flush()
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    user_id=user.id,
                    role_id=roles["owner"].id,
                )
            )
            doc = Document(
                id=uuid.uuid4(),
                owner_id=user.id,
                workspace_id=ws.id,
                filename="claim.txt",
                content_type="text/plain",
                storage_key=f"/tmp/claim_{uuid.uuid4().hex}",
                status="queued",
                file_size_bytes=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(doc)
            db.flush()
            dedup = f"{ws.id}:{doc.id}"
            job = IngestionJob(
                id=uuid.uuid4(),
                document_id=doc.id,
                workspace_id=ws.id,
                status="queued",
                attempts=0,
                deduplication_key=dedup,
                celery_task_id=str(uuid.uuid4()),
            )
            db.add(job)
            db.commit()
            db.expunge(job)
            return job
        finally:
            db.close()

    def _cleanup_job_tree(self, job_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            row = db.get(IngestionJob, job_id)
            if not row:
                return
            doc_id = row.document_id
            db.execute(delete(IngestionJob).where(IngestionJob.id == job_id))
            db.execute(delete(Document).where(Document.id == doc_id))
            db.commit()
        finally:
            db.close()

    def test_concurrent_celery_claim_single_winner(self) -> None:
        job = self._seed_queued_job()
        try:
            now = datetime.now(UTC)
            results: list[bool] = []
            barrier = threading.Barrier(2)

            def worker() -> None:
                s = SessionLocal()
                try:
                    barrier.wait()
                    r = claim_job_for_celery(
                        s,
                        job_id=job.id,
                        deduplication_key=job.deduplication_key,
                        celery_task_id=str(uuid.uuid4()),
                        now=now,
                    )
                    results.append(r)
                finally:
                    s.close()

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(sum(1 for x in results if x is True), 1)
            self.assertEqual(sum(1 for x in results if x is False), 1)

            verify = SessionLocal()
            try:
                j = verify.get(IngestionJob, job.id)
                self.assertIsNotNone(j)
                assert j is not None
                self.assertEqual(j.status, "processing")
                self.assertEqual(j.attempts, 1)
            finally:
                verify.close()
        finally:
            self._cleanup_job_tree(job.id)


if __name__ == "__main__":
    unittest.main()
