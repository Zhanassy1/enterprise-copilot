"""
Requeue stuck ingestion jobs: partial embeddings + stale worker lock or missed Celery redelivery.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.tasks.ingestion import ingest_document_task

logger = logging.getLogger("app.ingestion_stale_requeue")

_STALE_PICK_SQL = text(
    """
    SELECT
      j.id AS job_id,
      j.document_id AS document_id,
      j.workspace_id AS workspace_id,
      j.deduplication_key AS deduplication_key,
      j.status AS job_status
    FROM ingestion_jobs AS j
    INNER JOIN documents AS d ON d.id = j.document_id
    WHERE
      d.deleted_at IS NULL
      AND d.status IN ('processing', 'retrying')
      AND EXISTS (
        SELECT 1
        FROM document_chunks c
        WHERE c.document_id = d.id AND c.embedding_vector IS NULL
      )
      AND (
        (
          j.status = 'processing'
          AND j.locked_at IS NOT NULL
          AND j.locked_at < :stale_threshold
        )
        OR (
          j.status = 'retrying'
          AND j.available_at < :stale_threshold
        )
      )
    ORDER BY j.locked_at NULLS FIRST, j.available_at
    LIMIT 1
    FOR UPDATE OF j SKIP LOCKED
    """
)


@dataclass(frozen=True, slots=True)
class StaleRequeueResult:
    requeued: int
    job_ids: list[uuid.UUID]


def _requeue_one_job(db: Session, *, stale_threshold: datetime) -> uuid.UUID | None:
    row = (
        db.execute(
            _STALE_PICK_SQL,
            {"stale_threshold": stale_threshold},
        )
        .mappings()
        .first()
    )
    if not row:
        return None

    job_id: uuid.UUID = row["job_id"]
    document_id: uuid.UUID = row["document_id"]
    workspace_id: uuid.UUID = row["workspace_id"]
    deduplication_key: str = row["deduplication_key"]
    from_status: str = row["job_status"]

    reason = "stale_processing_lock" if from_status == "processing" else "stale_retrying"
    new_task_id = str(uuid.uuid4())
    if from_status == "processing":
        upd_sql = text(
            """
            UPDATE ingestion_jobs AS j
            SET
              status = 'queued',
              locked_at = NULL,
              available_at = :now,
              retry_after_seconds = NULL,
              error_message = NULL,
              celery_task_id = :new_task_id,
              attempts = GREATEST(0, COALESCE(j.attempts, 0) - 1)
            WHERE j.id = :job_id
              AND j.deduplication_key = :dedup
            RETURNING j.id
            """
        )
    else:
        upd_sql = text(
            """
            UPDATE ingestion_jobs AS j
            SET
              status = 'queued',
              locked_at = NULL,
              available_at = :now,
              retry_after_seconds = NULL,
              error_message = NULL,
              celery_task_id = :new_task_id
            WHERE j.id = :job_id
              AND j.deduplication_key = :dedup
            RETURNING j.id
            """
        )
    upd = db.execute(
        upd_sql,
        {
            "now": datetime.now(UTC),
            "new_task_id": new_task_id,
            "job_id": str(job_id),
            "dedup": deduplication_key,
        },
    ).first()
    if not upd:
        db.rollback()
        return None

    try:
        ingest_document_task.apply_async(
            kwargs={
                "document_id": str(document_id),
                "workspace_id": str(workspace_id),
                "ingestion_job_id": str(job_id),
                "deduplication_key": deduplication_key,
            },
            queue=settings.celery_ingestion_queue,
            task_id=new_task_id,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "stale requeue: apply_async failed job_id=%s document_id=%s",
            job_id,
            document_id,
        )
        raise
    db.commit()
    logger.info(
        "stale requeue: enqueued job_id=%s document_id=%s reason=%s",
        job_id,
        document_id,
        reason,
    )
    return job_id


def requeue_stale_ingestion_jobs(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> StaleRequeueResult:
    """
    Find at most ``limit`` jobs with partial embeddings and stale lock/schedule, requeue via Celery.
    Each requeue is its own short transaction: lock row, update, apply_async, commit.
    """
    now_ = now or datetime.now(UTC)
    minutes = max(1, int(settings.ingestion_stale_requeue_after_minutes))
    stale_threshold = now_ - timedelta(minutes=minutes)
    cap = max(1, int(limit))
    job_ids: list[uuid.UUID] = []
    for _ in range(cap):
        jid = _requeue_one_job(db, stale_threshold=stale_threshold)
        if jid is None:
            break
        job_ids.append(jid)
    return StaleRequeueResult(requeued=len(job_ids), job_ids=job_ids)
