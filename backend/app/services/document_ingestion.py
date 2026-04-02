from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, IngestionJob
from app.models.workspace import Workspace
from app.schemas.documents import DocumentIngestOut, DocumentOut
from app.services.antivirus import scan_uploaded_file_safe
from app.services.document_indexing import DocumentIndexingService
from app.services.storage.base import StorageService, StoredFile
from app.services.usage_metering import (
    EVENT_DOCUMENT_UPLOAD,
    EVENT_UPLOAD_BYTES,
    assert_quota,
    max_concurrent_ingestion_jobs_for_workspace,
    record_event,
)
from app.tasks.ingestion import ingest_document_task

logger = logging.getLogger(__name__)


def _env_truthy(name: str) -> bool | None:
    if name not in os.environ:
        return None
    return os.environ[name].strip().lower() in ("1", "true", "yes")


def _effective_ingestion_pipeline_flags() -> tuple[bool, bool]:
    """
    Normal path uses frozen ``settings``. Under pytest, ``conftest`` imports the app before
    ``test_api_integration`` mutates ``os.environ``, so the singleton can be stale; honor env
    for integration runs (never in production).
    """
    async_on = settings.ingestion_async_enabled
    allow_sync = settings.allow_sync_ingestion_for_dev
    if (
        os.environ.get("RUN_INTEGRATION_TESTS") == "1"
        and settings.environment.lower().strip() != "production"
    ):
        v_async = _env_truthy("INGESTION_ASYNC_ENABLED")
        if v_async is not None:
            async_on = v_async
        v_allow = _env_truthy("ALLOW_SYNC_INGESTION_FOR_DEV")
        if v_allow is not None:
            allow_sync = v_allow
    return async_on, allow_sync

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}


def _workspace_upload_advisory_lock_key(workspace_id: uuid.UUID) -> int:
    return int(workspace_id.int % (1 << 63))


def validate_upload(file: UploadFile) -> None:
    raw_name = (file.filename or "").strip()
    if not raw_name or raw_name.endswith((".", "/")):
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Single allowed extension at end only (reject e.g. contract.pdf.exe)
    if not re.match(r"^[^\\/]+\.(pdf|docx|txt)$", raw_name, flags=re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Filename must end with .pdf, .docx or .txt only")
    suffix = Path(raw_name).suffix.lower()
    content_type = (file.content_type or "").lower().strip()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Allowed: pdf, docx, txt")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")
    # MIME sniffing: verify magic bytes for binary formats.
    if not file.file:
        return
    try:
        pos = file.file.tell()
        header = file.file.read(8) or b""
        file.file.seek(pos)
    except Exception as e:
        logger.debug("upload magic-byte read skipped (stream error): %s", e)
        return
    if suffix == ".pdf" and not header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File content does not match PDF format")
    if suffix == ".docx" and not header.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="File content does not match DOCX format")
    if suffix == ".pdf":
        try:
            file.file.seek(0)
            from pypdf import PdfReader

            reader = PdfReader(file.file)
            if getattr(reader, "is_encrypted", False) and reader.is_encrypted:
                raise HTTPException(status_code=400, detail="Encrypted PDFs are not supported")
        except HTTPException:
            raise
        except Exception as e:
            logger.info("PDF validation failed: %s", e)
            raise HTTPException(status_code=400, detail="Invalid or unreadable PDF") from None
        finally:
            try:
                file.file.seek(0)
            except Exception:
                pass


class DocumentIngestionService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self._indexer: DocumentIndexingService | None = None

    @property
    def indexer(self) -> DocumentIndexingService:
        if self._indexer is None:
            self._indexer = DocumentIndexingService(self.db, self.storage)
        return self._indexer

    def list_documents(self, workspace_id: uuid.UUID) -> list[tuple[Document, str | None]]:
        docs = list(
            self.db.scalars(
                select(Document)
                .where(
                    Document.workspace_id == workspace_id,
                    Document.deleted_at.is_(None),
                )
                .order_by(Document.created_at.desc())
            ).all()
        )
        if not docs:
            return []
        doc_ids = [d.id for d in docs]
        rows = self.db.execute(
            select(IngestionJob.document_id, IngestionJob.status, IngestionJob.created_at)
            .where(IngestionJob.document_id.in_(doc_ids), IngestionJob.workspace_id == workspace_id)
            .order_by(IngestionJob.document_id, IngestionJob.created_at.desc())
        ).all()
        latest: dict[uuid.UUID, str] = {}
        for row in rows:
            if row.document_id not in latest:
                latest[row.document_id] = row.status
        return [(d, latest.get(d.id)) for d in docs]

    def latest_ingestion_job_status(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> str | None:
        job = self.db.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.document_id == document_id,
                IngestionJob.workspace_id == workspace_id,
            )
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return job.status if job else None

    def get_document(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )

    def _save_and_scan(self, file: UploadFile) -> StoredFile:
        stored = self.storage.save_upload(file.file, file.filename or "upload.bin")
        if stored.size_bytes > MAX_UPLOAD_BYTES:
            self.storage.delete(stored.storage_key)
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")
        with self.storage.local_path(stored.storage_key) as local_file:
            scan_uploaded_file_safe(local_file)
        return stored

    def _find_duplicate(self, workspace: Workspace, stored: StoredFile) -> Document | None:
        return self.db.scalar(
            select(Document).where(
                Document.workspace_id == workspace.id,
                Document.sha256 == stored.sha256,
                Document.deleted_at.is_(None),
                Document.status == "ready",
            )
        )

    def _check_quota(self, user_id: uuid.UUID, workspace: Workspace, stored: StoredFile) -> None:
        assert_quota(
            self.db,
            workspace_id=workspace.id,
            user_id=user_id,
            request_increment=1,
            upload_bytes_increment=int(stored.size_bytes),
        )

    def _create_document_record(
        self,
        user_id: uuid.UUID,
        workspace: Workspace,
        file: UploadFile,
        stored: StoredFile,
    ) -> Document:
        doc = Document(
            id=uuid.uuid4(),
            owner_id=user_id,
            workspace_id=workspace.id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            storage_key=stored.storage_key,
            status="queued",
            file_size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            parser_version="v1",
            indexed_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def _enqueue_ingestion_job(self, workspace: Workspace, stored: StoredFile, doc: Document) -> int:
        ingestion_async_enabled, allow_sync_ingestion_for_dev = _effective_ingestion_pipeline_flags()
        if ingestion_async_enabled:
            active_jobs = self.db.scalar(
                select(func.count())
                .select_from(IngestionJob)
                .where(
                    IngestionJob.workspace_id == workspace.id,
                    IngestionJob.status.in_(["queued", "processing", "retrying"]),
                )
            )
            max_jobs = max_concurrent_ingestion_jobs_for_workspace(self.db, workspace.id)
            if int(active_jobs or 0) >= max_jobs:
                self.storage.delete(stored.storage_key)
                self.db.rollback()
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many concurrent ingestion jobs for this workspace (limit {max_jobs})",
                )
            deduplication_key = f"{workspace.id}:{doc.id}"
            celery_task_id = str(uuid.uuid4())
            job = IngestionJob(
                document_id=doc.id,
                workspace_id=workspace.id,
                status="queued",
                attempts=0,
                deduplication_key=deduplication_key,
                celery_task_id=celery_task_id,
            )
            self.db.add(job)
            self.db.flush()
            # Commit before enqueue: worker uses a new DB connection; uncommitted rows are invisible (avoids perpetual "queued" with eager/sync apply).
            self.db.commit()
            self.db.refresh(doc)
            self.db.refresh(job)
            try:
                ingest_document_task.apply_async(
                    kwargs={
                        "document_id": str(doc.id),
                        "workspace_id": str(workspace.id),
                        "ingestion_job_id": str(job.id),
                        "deduplication_key": deduplication_key,
                    },
                    queue=settings.celery_ingestion_queue,
                    task_id=celery_task_id,
                )
            except Exception as exc:
                doc_row = self.db.get(Document, doc.id)
                job_row = self.db.get(IngestionJob, job.id)
                if doc_row is not None and job_row is not None:
                    doc_row.status = "failed"
                    doc_row.error_message = f"Failed to enqueue ingestion task: {exc}"
                    job_row.status = "failed"
                    job_row.error_message = str(exc)
                    self.db.add(doc_row)
                    self.db.add(job_row)
                    self.db.commit()
                raise HTTPException(status_code=503, detail="Failed to enqueue ingestion task") from exc
            self.db.refresh(doc)
            return 0
        # Sync path is dev-only; never index in-process in production (even if misconfigured).
        if settings.environment.lower().strip() == "production":
            self.storage.delete(stored.storage_key)
            self.db.rollback()
            raise HTTPException(
                status_code=503,
                detail="In-process ingestion is disabled in production; use INGESTION_ASYNC_ENABLED=1 and the Celery worker.",
            )
        if not allow_sync_ingestion_for_dev:
            self.storage.delete(stored.storage_key)
            self.db.rollback()
            raise HTTPException(
                status_code=503,
                detail="Async ingestion required: set INGESTION_ASYNC_ENABLED=1 and run the Celery worker, "
                "or for local development only set ALLOW_SYNC_INGESTION_FOR_DEV=1 with ENVIRONMENT=local",
            )
        chunks_created = self.indexer.run(doc)
        self.db.commit()
        self.db.refresh(doc)
        return chunks_created

    def _record_upload_events(
        self,
        user_id: uuid.UUID,
        workspace: Workspace,
        doc: Document,
        stored: StoredFile,
    ) -> None:
        record_event(
            self.db,
            workspace_id=workspace.id,
            user_id=user_id,
            event_type=EVENT_DOCUMENT_UPLOAD,
            quantity=1,
            unit="count",
            metadata={"document_id": str(doc.id), "filename": doc.filename},
        )
        record_event(
            self.db,
            workspace_id=workspace.id,
            user_id=user_id,
            event_type=EVENT_UPLOAD_BYTES,
            quantity=int(stored.size_bytes),
            unit="bytes",
            metadata={"document_id": str(doc.id)},
        )
        self.db.commit()

    def upload_document(self, user_id: uuid.UUID, workspace: Workspace, file: UploadFile) -> DocumentIngestOut:
        validate_upload(file)
        stored = self._save_and_scan(file)
        should_cleanup_storage = True
        try:
            dup = self._find_duplicate(workspace, stored)
            if dup:
                return DocumentIngestOut(document=DocumentOut.from_document(dup), chunks_created=0)
            # Per-workspace transaction lock: without it, two concurrent uploads can both pass
            # assert_quota() (same usage snapshot) and both insert rows (TOCTOU vs document cap and usage events).
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": _workspace_upload_advisory_lock_key(workspace.id)},
            )
            self._check_quota(user_id, workspace, stored)
            doc = self._create_document_record(user_id, workspace, file, stored)
            # Ownership is transferred to persisted document record.
            should_cleanup_storage = False
            chunks_created = self._enqueue_ingestion_job(workspace, stored, doc)
            self._record_upload_events(user_id, workspace, doc, stored)
            return DocumentIngestOut(
                document=DocumentOut.from_document(doc),
                chunks_created=chunks_created,
            )
        finally:
            if should_cleanup_storage:
                self.storage.delete(stored.storage_key)

    def delete_document(self, document: Document, workspace_id: uuid.UUID) -> None:
        if document.workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        document.deleted_at = datetime.now(timezone.utc)
        self.db.add(document)
        self.db.commit()
