from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, IngestionJob
from app.models.workspace import Workspace
from app.schemas.documents import DocumentIngestOut, DocumentOut
from app.services.document_indexing import DocumentIndexingService
from app.services.storage.base import StorageService
from app.services.usage_metering import (
    EVENT_DOCUMENT_UPLOAD,
    EVENT_UPLOAD_BYTES,
    assert_quota,
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
    suffix = Path(file.filename or "").suffix.lower()
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


class DocumentIngestionService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self.indexer = DocumentIndexingService(db, storage)

    def list_documents(self, workspace_id: uuid.UUID) -> list[Document]:
        return self.db.scalars(
            select(Document).where(Document.workspace_id == workspace_id).order_by(Document.created_at.desc())
        ).all()

    def get_document(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        return self.db.scalar(
            select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
        )

    def upload_document(self, user_id: uuid.UUID, workspace: Workspace, file: UploadFile) -> DocumentIngestOut:
        validate_upload(file)
        stored = self.storage.save_upload(file.file, file.filename or "upload.bin")
        if stored.size_bytes > MAX_UPLOAD_BYTES:
            self.storage.delete(stored.storage_path)
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")
        assert_quota(
            self.db,
            workspace_id=workspace.id,
            request_increment=1,
            upload_bytes_increment=int(stored.size_bytes),
        )

        doc = Document(
            id=uuid.uuid4(),
            owner_id=user_id,
            workspace_id=workspace.id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            storage_path=stored.storage_path,
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
        self.storage.delete(document.storage_path)
        self.db.delete(document)
        self.db.commit()
