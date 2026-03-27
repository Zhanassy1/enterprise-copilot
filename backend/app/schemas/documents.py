import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str | None = None
    status: str
    error_message: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    page_count: int | None = None
    language: str | None = None
    parser_version: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, doc) -> "DocumentOut":
        return cls(
            id=doc.id,
            filename=doc.filename,
            content_type=doc.content_type,
            status=doc.status,
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
    updated: int


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

