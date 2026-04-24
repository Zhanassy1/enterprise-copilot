from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class IngestionSettings(BaseModel):
    celery_ingestion_queue: str = Field(default="ingestion")

    # Async ingestion pipeline (required in production; sync only for local dev when allowed)
    ingestion_async_enabled: bool = Field(default=False)
    allow_sync_ingestion_for_dev: bool = Field(
        default=False,
        description="If True and ENVIRONMENT=local, allow sync indexing on upload when INGESTION_ASYNC_ENABLED=0.",
    )
    ingestion_max_attempts: int = Field(default=5, ge=1, le=50)
    ingestion_retry_backoff_seconds: int = Field(default=5, ge=1, le=300)
    ingestion_retry_backoff_max_seconds: int = Field(default=300, ge=1, le=3600)
    ingestion_task_soft_time_limit_seconds: int = Field(default=300, ge=5, le=7200)
    ingestion_task_time_limit_seconds: int = Field(default=360, ge=10, le=7200)
    ingestion_dead_letter_enabled: bool = Field(default=True)
    document_retention_days_after_soft_delete: int = Field(
        default=30,
        ge=1,
        le=3650,
        description="Hard-delete soft-deleted documents older than this (maintenance task).",
    )
    immediate_hard_delete_after_soft_delete: bool = Field(
        default=False,
        description="If True, enqueue hard delete (storage + DB row) right after API soft-delete.",
    )
    chunk_size: int = Field(
        default=800,
        ge=200,
        le=8000,
        description="Target max characters per chunk during document indexing (see chunking.chunk_text).",
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=2000,
        description="Character overlap between consecutive chunks.",
    )
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
        description="Max texts per embedding encode + DB update batch during indexing (memory and retry granularity).",
    )

    # PDF: native text vs scanned / OCR (AWS Textract)
    pdf_ocr_enabled: bool = Field(default=False, description="Run cloud OCR when native PDF text is weak or empty.")
    pdf_ocr_provider: Literal["none", "textract"] = Field(default="none")
    pdf_min_chars_per_page: int = Field(
        default=20,
        ge=0,
        le=5000,
        description="Page is 'trivially empty' if stripped text has fewer characters than this.",
    )
    pdf_min_mean_chars_per_page: int = Field(
        default=50,
        ge=0,
        le=50000,
        description="Below this mean (pypdf), extraction is considered weak.",
    )
    pdf_max_empty_page_ratio: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Above this ratio of trivially empty pages, extraction is weak.",
    )
    pdf_ocr_staging_bucket: str = Field(
        default="",
        description="S3 bucket for temporary upload when storage is local (Textract requires S3).",
    )
    pdf_ocr_staging_prefix: str = Field(default="ocr-staging", description="Key prefix under staging bucket.")
    textract_poll_interval_seconds: float = Field(default=1.0, ge=0.2, le=30.0)
    textract_max_wait_seconds: float = Field(default=300.0, ge=5.0, le=3600.0)

    @model_validator(mode="after")
    def overlap_lt_chunk_size(self) -> Self:
        if int(self.chunk_overlap) >= int(self.chunk_size):
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self
