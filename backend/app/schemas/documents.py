import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str | None = None
    created_at: datetime


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

