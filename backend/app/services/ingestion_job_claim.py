"""PostgreSQL-only atomic claim for ingestion jobs (Celery worker)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def claim_job_for_celery(
    db: Session,
    *,
    job_id: uuid.UUID,
    deduplication_key: str,
    celery_task_id: str,
    now: datetime,
) -> bool:
    """
    Atomically transition queued|retrying job to processing and document to processing; commit.
    Returns True if exactly one row was updated; False if another worker claimed or state incompatible.
    """
    row = (
        db.execute(
            text(
                """
                UPDATE ingestion_jobs AS j
                SET
                    status = 'processing',
                    locked_at = :now,
                    attempts = COALESCE(j.attempts, 0) + 1,
                    celery_task_id = :celery_task_id,
                    error_message = NULL,
                    retry_after_seconds = NULL
                WHERE j.id = :job_id
                  AND j.deduplication_key = :dedup
                  AND j.status IN ('queued', 'retrying')
                  AND j.available_at <= :now
                RETURNING j.document_id
                """
            ),
            {
                "now": now,
                "celery_task_id": celery_task_id,
                "job_id": job_id,
                "dedup": deduplication_key,
            },
        )
        .mappings()
        .first()
    )
    if not row:
        db.rollback()
        return False

    doc_id = row["document_id"]
    db.execute(
        text(
            """
            UPDATE documents
            SET status = 'processing', error_message = NULL
            WHERE id = :doc_id
            """
        ),
        {"doc_id": doc_id},
    )
    db.commit()
    return True
