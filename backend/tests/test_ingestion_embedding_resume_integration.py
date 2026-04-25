"""
PostgreSQL: resume indexing after partial NULL embeddings; stale ingestion requeue.

Run: RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_ingestion_embedding_resume_integration.py -v
"""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import delete

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, IngestionJob
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.document_indexing import DocumentIndexingService
from app.services.ingestion_stale_requeue import requeue_stale_ingestion_jobs
from app.services.retrieval.chunk_search_aux import build_chunk_search_aux
from app.services.text_extraction import ExtractedDocument
from app.services.workspace_service import ensure_default_roles


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class IngestionEmbeddingResumeIntegrationTests(unittest.TestCase):
    @staticmethod
    def _indexing_meta() -> dict:
        return {
            "indexing": {
                "chunk_size": int(settings.chunk_size),
                "chunk_overlap": int(settings.chunk_overlap),
                "parser_version": "v1",
            }
        }

    def _seed_user_ws(self):
        """Returns (user_id, workspace_id)."""
        db = SessionLocal()
        try:
            roles = ensure_default_roles(db)
            uid = uuid.uuid4()
            user = User(
                id=uid,
                email=f"embed_resume_{uid.hex[:10]}@example.com",
                password_hash=hash_password("EmbResTest1!"),
                full_name="Embed Resume Test",
            )
            db.add(user)
            db.flush()
            ws = Workspace(
                id=uuid.uuid4(),
                name="Emb WS",
                slug=f"emb-ws-{uuid.uuid4().hex[:10]}",
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
            db.commit()
            return user.id, ws.id
        finally:
            db.close()

    def _cleanup(self, job_id: uuid.UUID | None, document_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            if job_id is not None:
                db.execute(delete(IngestionJob).where(IngestionJob.id == job_id))
            db.execute(delete(Document).where(Document.id == document_id))
            db.commit()
        finally:
            db.close()

    def test_embed_pending_path_marks_ready(self) -> None:
        user_id, ws_id = self._seed_user_ws()
        document_id = uuid.uuid4()
        job_id: uuid.UUID | None = None
        dim = 384
        t1, t2 = "chunk one alpha text", "chunk two beta text"
        db = SessionLocal()
        try:
            doc = Document(
                id=document_id,
                owner_id=user_id,
                workspace_id=ws_id,
                filename="t.txt",
                content_type="text/plain",
                storage_key=f"/tmp/emb_res_{document_id.hex[:12]}",
                status="retrying",
                error_message="simulated",
                file_size_bytes=10,
                extraction_meta=self._indexing_meta(),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(doc)
            db.flush()
            for i, t in enumerate((t1, t2)):
                db.add(
                    DocumentChunk(
                        document_id=doc.id,
                        chunk_index=i,
                        text=t,
                        page_number=1,
                        paragraph_index=0,
                        chunk_search_aux=build_chunk_search_aux(t),
                        embedding_vector=None,
                    )
                )
            db.commit()
        finally:
            db.close()

        try:
            s2 = SessionLocal()
            try:
                doc2 = s2.get(Document, document_id)
                assert doc2 is not None
                storage = MagicMock()
                with (
                    patch("app.services.document_indexing.get_embedding_dim", return_value=dim),
                    patch(
                        "app.services.document_indexing.embed_texts",
                        return_value=[[0.1] * dim, [0.2] * dim],
                    ),
                ):
                    svc = DocumentIndexingService(s2, storage)
                    out = svc.run(doc2)
                self.assertEqual(out, 2)
                s2.refresh(doc2)
                self.assertEqual(doc2.status, "ready")
                self.assertIsNotNone(doc2.indexed_at)
            finally:
                s2.close()
        finally:
            self._cleanup(job_id, document_id)

    def test_embed_fails_after_placeholder_commit_second_run_ready(self) -> None:
        """Simulates: chunks persisted + commit, embedding fails, Celery would set retrying, resume completes."""
        user_id, ws_id = self._seed_user_ws()
        document_id = uuid.uuid4()
        job_id: uuid.UUID | None = None
        dim = 384
        t_text = "x"
        extracted = ExtractedDocument(text="one\n\ntwo\n\nthree", page_count=1, language="en")
        p = None
        db = SessionLocal()
        try:
            p = Path(tempfile.mkdtemp()) / "resume.txt"
            p.write_text(t_text, encoding="utf-8")
            doc = Document(
                id=document_id,
                owner_id=user_id,
                workspace_id=ws_id,
                filename="resume.txt",
                content_type="text/plain",
                storage_key=f"/tmp/k_{document_id.hex[:12]}",
                status="processing",
                file_size_bytes=len(t_text.encode("utf-8")),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(doc)
            db.commit()
        finally:
            db.close()
        try:
            storage = MagicMock()
            storage.local_path = MagicMock()
            storage.local_path.return_value.__enter__ = lambda *_: p
            storage.local_path.return_value.__exit__ = lambda *_a, _b, _c, _d: None
            s1 = SessionLocal()
            try:
                d1 = s1.get(Document, document_id)
                assert d1 is not None
                embed_calls = [0]

                def _blow_on_first(_texts, **_kw):
                    embed_calls[0] += 1
                    if embed_calls[0] == 1:
                        raise RuntimeError("simulated embed failure")
                    return [[0.01 * (i + 1) for _k in range(dim)] for i in range(len(_texts))]

                chunk_three = ["alpha segment", "beta segment", "gamma segment"]
                with (
                    patch("app.services.document_indexing.get_embedding_dim", return_value=dim),
                    patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=None),
                    patch("app.services.document_indexing.chunk_text", return_value=chunk_three),
                    patch(
                        "app.services.document_indexing.extract_text_metadata_from_file",
                        return_value=extracted,
                    ),
                    patch("app.services.document_indexing.embed_texts", side_effect=_blow_on_first),
                ):
                    svc = DocumentIndexingService(s1, storage)
                    with self.assertRaises(RuntimeError):
                        svc.run(d1)
                s1.commit()
                d1.status = "retrying"
                s1.add(d1)
                s1.commit()
            finally:
                s1.close()
            s2 = SessionLocal()
            try:
                d2 = s2.get(Document, document_id)
                assert d2 is not None
                storage2 = MagicMock()
                storage2.local_path = MagicMock()
                storage2.local_path.return_value.__enter__ = lambda *_: p
                storage2.local_path.return_value.__exit__ = lambda *_a, _b, _c, _d: None
                with (
                    patch("app.services.document_indexing.get_embedding_dim", return_value=dim),
                    patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=None),
                    patch(
                        "app.services.document_indexing.embed_texts",
                        return_value=[[0.1] * dim for _ in range(3)],
                    ),
                ):
                    svc2 = DocumentIndexingService(s2, storage2)
                    out = svc2.run(d2)
                self.assertEqual(out, 3)
                s2.refresh(d2)
                self.assertEqual(d2.status, "ready")
            finally:
                s2.close()
        finally:
            if p is not None:
                try:
                    p.unlink()
                    p.parent.rmdir()
                except OSError:
                    pass
            self._cleanup(job_id, document_id)

    def test_stale_processing_lock_requeues_and_calls_apply_async(self) -> None:
        user_id, ws_id = self._seed_user_ws()
        document_id = uuid.uuid4()
        job_id = uuid.uuid4()
        t1 = "stale lock chunk"
        now = datetime.now(UTC)
        stale_lock = now - timedelta(hours=1)
        try:
            db = SessionLocal()
            doc = Document(
                id=document_id,
                owner_id=user_id,
                workspace_id=ws_id,
                filename="s.txt",
                content_type="text/plain",
                storage_key=f"/tmp/stale_{document_id.hex[:12]}",
                status="processing",
                file_size_bytes=8,
                extraction_meta=self._indexing_meta(),
                created_at=now,
                updated_at=now,
            )
            db.add(doc)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=0,
                    text=t1,
                    page_number=1,
                    paragraph_index=0,
                    chunk_search_aux=build_chunk_search_aux(t1),
                    embedding_vector=None,
                )
            )
            dedup = f"{ws_id}:{doc.id}"
            job = IngestionJob(
                id=job_id,
                document_id=doc.id,
                workspace_id=ws_id,
                status="processing",
                attempts=2,
                deduplication_key=dedup,
                celery_task_id=str(uuid.uuid4()),
                locked_at=stale_lock,
                available_at=now,
            )
            db.add(job)
            db.commit()
            db.close()

            s_run = SessionLocal()
            try:
                with patch(
                    "app.services.ingestion_stale_requeue.ingest_document_task.apply_async"
                ) as p_async:
                    r = requeue_stale_ingestion_jobs(s_run, now=now, limit=5)
                self.assertEqual(r.requeued, 1)
                self.assertEqual(r.job_ids[0], job_id)
                p_async.assert_called_once()
            finally:
                s_run.close()
            s_ver = SessionLocal()
            try:
                j = s_ver.get(IngestionJob, job_id)
                self.assertIsNotNone(j)
                assert j is not None
                self.assertEqual(j.status, "queued")
                self.assertIsNone(j.locked_at)
                self.assertEqual(j.attempts, 1)
            finally:
                s_ver.close()
        finally:
            self._cleanup(job_id, document_id)


if __name__ == "__main__":
    unittest.main()
