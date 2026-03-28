from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
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
    record_event,
)
from app.tasks.ingestion import ingest_document_task

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}

_SUSPICIOUS_DOUBLE_EXT = re.compile(r"\.(pdf|docx|txt)\.[^.\\/]+$", re.IGNORECASE)


def validate_filename_rules(filename: str | None) -> None:
    name = (filename or "").strip()
    if not name or "\x00" in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    norm = name.replace("\\", "/")
    if ".." in norm or norm.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = Path(name).name
    if _SUSPICIOUS_DOUBLE_EXT.search(base):
        raise HTTPException(status_code=400, detail="Invalid filename (suspicious double extension)")


def read_upload_body_capped(stream, max_bytes: int) -> bytes:
    out = bytearray()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        out.extend(chunk)
        if len(out) > max_bytes:
            raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes} bytes)")
    return bytes(out)


def validate_upload_bytes(filename: str | None, content_type: str | None, body: bytes) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Allowed: pdf, docx, txt")
    ct = (content_type or "").lower().strip()
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")
    if suffix == ".txt":
        return
    if suffix == ".pdf":
        if not body.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="File content does not match PDF format")
        try:
            reader = PdfReader(io.BytesIO(body))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or unreadable PDF")
        if getattr(reader, "is_encrypted", False):
            raise HTTPException(
                status_code=400,
                detail="Encrypted PDFs are not supported; remove password protection first",
            )
        n_pages = len(reader.pages)
        if n_pages > int(settings.max_pdf_pages_per_upload):
            raise HTTPException(
                status_code=400,
                detail=f"PDF exceeds maximum page count ({int(settings.max_pdf_pages_per_upload)})",
            )
        return
    if suffix == ".docx":
        if not body.startswith(b"PK"):
            raise HTTPException(status_code=400, detail="File content does not match DOCX format")


def validate_upload(file: UploadFile) -> None:
    """Validate an upload stream (consumes `file.file`). Prefer `upload_document` for API handlers."""
    validate_filename_rules(file.filename)
    max_bytes = int(settings.max_upload_bytes_per_file)
    if not file.file:
        return
    body = read_upload_body_capped(file.file, max_bytes)
    validate_upload_bytes(file.filename, file.content_type, body)


class DocumentIngestionService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self.indexer = DocumentIndexingService(db, storage)

    def list_documents(self, workspace_id: uuid.UUID) -> list[Document]:
        return self.db.scalars(
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
        ).all()

    def get_document(self, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )

    def upload_document(self, user_id: uuid.UUID, workspace: Workspace, file: UploadFile) -> DocumentIngestOut:
        max_bytes = int(settings.max_upload_bytes_per_file)
        if not file.file:
            raise HTTPException(status_code=400, detail="Empty upload")
        body = read_upload_body_capped(file.file, max_bytes)
        validate_filename_rules(file.filename)
        validate_upload_bytes(file.filename, file.content_type, body)
        stored = self.storage.save_upload(io.BytesIO(body), file.filename or "upload.bin")

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

        n_active = self.db.scalar(
            select(func.count())
            .select_from(IngestionJob)
            .where(
                IngestionJob.workspace_id == workspace.id,
                IngestionJob.status.in_(["queued", "processing", "retrying"]),
            )
        )
        if int(n_active or 0) >= int(settings.max_concurrent_ingestion_jobs_per_workspace):
            self.storage.delete(stored.storage_key)
            raise HTTPException(
                status_code=429,
                detail="Too many concurrent ingestion jobs for this workspace; try again later.",
            )

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
        document.deleted_at = datetime.now(timezone.utc)
        self.db.add(document)
        self.db.commit()
