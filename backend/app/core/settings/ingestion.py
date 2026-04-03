from pydantic import BaseModel, Field


class IngestionSettings(BaseModel):
    celery_ingestion_queue: str = Field(default="ingestion")

    # Async ingestion pipeline (required in production; sync only for local dev when allowed)
    ingestion_async_enabled: bool = Field(default=False)
    allow_sync_ingestion_for_dev: bool = Field(
        default=False,
        description="If True and ENVIRONMENT=local, allow sync indexing on upload when INGESTION_ASYNC_ENABLED=0.",
    )
    ingestion_worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
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
