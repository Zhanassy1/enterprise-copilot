"""Canonical ingestion pipeline status strings (document + job share vocabulary in API)."""

# Celery ingestion + indexing task writes these values to documents.ingestion_jobs.status
# and documents.documents.status (same phase names where applicable).
INGESTION_JOB_STATUSES: tuple[str, ...] = ("queued", "processing", "retrying", "ready", "failed")

# Document catalog status during/after pipeline (soft-delete uses deleted_at, not always a "deleted" status).
DOCUMENT_PIPELINE_STATUSES: tuple[str, ...] = ("queued", "processing", "retrying", "ready", "failed")
