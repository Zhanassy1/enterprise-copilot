import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DocumentOut(BaseModel):
    id: uuid.UUID
    uploaded_by: uuid.UUID | None = Field(
        default=None,
        description="User who uploaded the document (DB owner_id); not used for authorization — scope is workspace_id.",
    )
    filename: str
    content_type: str | None = None
    status: str
    ingestion_job_status: str | None = Field(
        default=None,
        description="Latest ingestion job status for this document (if any), same vocabulary as IngestionJob.status.",
    )
    error_message: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    page_count: int | None = None
    language: str | None = None
    parser_version: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, doc, *, ingestion_job_status: str | None = None) -> "DocumentOut":
        return cls(
            id=doc.id,
            uploaded_by=getattr(doc, "owner_id", None),
            filename=doc.filename,
            content_type=doc.content_type,
            status=doc.status,
            ingestion_job_status=ingestion_job_status,
            error_message=doc.error_message,
            file_size_bytes=doc.file_size_bytes,
            sha256=doc.sha256,
            page_count=doc.page_count,
            language=doc.language,
            parser_version=doc.parser_version,
            indexed_at=doc.indexed_at,
            created_at=doc.created_at,
        )


class DocumentIngestOut(BaseModel):
    document: DocumentOut
    chunks_created: int


class ReindexEmbeddingsOut(BaseModel):
    updated: int = 0
    mode: Literal["sync", "async"] = "sync"
    task_id: str | None = None
    message: str | None = None


class IngestionJobOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    status: str
    attempts: int
    deduplication_key: str
    celery_task_id: str | None = None
    error_message: str | None = None
    retry_after_seconds: int | None = None
    dead_lettered_at: datetime | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_job(cls, job) -> "IngestionJobOut":
        return cls(
            id=job.id,
            document_id=job.document_id,
            workspace_id=job.workspace_id,
            status=job.status,
            attempts=int(job.attempts or 0),
            deduplication_key=job.deduplication_key,
            celery_task_id=job.celery_task_id,
            error_message=job.error_message,
            retry_after_seconds=job.retry_after_seconds,
            dead_lettered_at=job.dead_lettered_at,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )


class DocumentSummaryOut(BaseModel):
    document_id: uuid.UUID
    summary: str


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query", mode="after")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        return cleaned


class SearchHit(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    source_filename: str | None = None
    citation_anchor: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    text: str
    score: float


class SearchOut(BaseModel):
    answer: str | None = None
    details: str | None = None
    decision: Literal["answer", "clarify", "insufficient_context"] = "answer"
    confidence: float = 0.0
    clarifying_question: str | None = None
    next_step: str | None = None
    evidence_collapsed_by_default: bool = True
    hits: list[SearchHit]

