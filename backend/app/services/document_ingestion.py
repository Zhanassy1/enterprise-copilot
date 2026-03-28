from __future__ import annotations

import uuid
from datetime import datetime, timezone
import io
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, IngestionJob
from app.models.workspace import Workspace
from app.schemas.documents import DocumentIngestOut, DocumentOut
from app.services.antivirus import scan_uploaded_file_safe
from app.services.document_indexing import DocumentIndexingService
from app.services.storage.base import StorageService
from app.services.usage_metering import (
    EVENT_DOCUMENT_UPLOAD,
    EVENT_UPLOAD_BYTES,
    assert_quota,
    max_concurrent_ingestion_jobs_for_workspace,
    record_event,
)
from app.tasks.ingestion import ingest_document_task

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}


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
    except Exception:
        return
    if suffix == ".pdf" and not header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File content does not match PDF format")
    if suffix == ".docx" and not header.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="File content does not match DOCX format")
    if suffix == ".pdf":
        try:
            pos = file.file.tell()
            file.file.seek(0)
            blob = file.file.read() or b""
            file.file.seek(pos)
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(blob))
            if getattr(reader, "is_encrypted", False) and reader.is_encrypted:
                raise HTTPException(status_code=400, detail="Encrypted PDFs are not supported")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or unreadable PDF") from None


class DocumentIngestionService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self.indexer = DocumentIndexingService(db, storage)

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

    def upload_document(self, user_id: uuid.UUID, workspace: Workspace, file: UploadFile) -> DocumentIngestOut:
        validate_upload(file)
        stored = self.storage.save_upload(file.file, file.filename or "upload.bin")
        if stored.size_bytes > MAX_UPLOAD_BYTES:
            self.storage.delete(stored.storage_key)
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")

        with self.storage.local_path(stored.storage_key) as local_file:
            scan_uploaded_file_safe(local_file)

        dup = self.db.scalar(
            select(Document).where(
                Document.workspace_id == workspace.id,
                Document.sha256 == stored.sha256,
                Document.deleted_at.is_(None),
                Document.status == "ready",
            )
        )
        if dup:
            self.storage.delete(stored.storage_key)
            return DocumentIngestOut(document=DocumentOut.from_document(dup), chunks_created=0)

        assert_quota(
            self.db,
            workspace_id=workspace.id,
            user_id=user_id,
            request_increment=1,
            upload_bytes_increment=int(stored.size_bytes),
        )

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

        if settings.ingestion_async_enabled:
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
                doc.status = "failed"
                doc.error_message = f"Failed to enqueue ingestion task: {exc}"
                job.status = "failed"
                job.error_message = str(exc)
                self.db.add(doc)
                self.db.add(job)
                self.db.commit()
                raise HTTPException(status_code=503, detail="Failed to enqueue ingestion task") from exc
            chunks_created = 0
        else:
            if not settings.allow_sync_ingestion_for_dev:
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
        return DocumentIngestOut(
            document=DocumentOut.from_document(doc),
            chunks_created=chunks_created,
        )

    def delete_document(self, document: Document) -> None:
        document.deleted_at = datetime.now(timezone.utc)
        self.db.add(document)
        self.db.commit()
