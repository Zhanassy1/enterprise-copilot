from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from celery import Task
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, IngestionJob
from app.services.audit import write_audit_log
from app.services.document_indexing import (
    DocumentIndexingService,
    reindex_null_embeddings_for_workspace,
)
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)

ingestion_terminal_failures_total = 0
ingestion_retries_total = 0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _truncate_error(exc: Exception, max_length: int = 3000) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[:max_length]


def _retry_delay_seconds(attempt_number: int) -> int:
    base = int(settings.ingestion_retry_backoff_seconds)
    max_backoff = int(settings.ingestion_retry_backoff_max_seconds)
    raw = base * (2 ** max(0, attempt_number - 1))
    return max(1, min(max_backoff, raw))


def _mark_document_missing(job: IngestionJob) -> None:
    now = _utcnow()
    job.status = "failed"
    job.error_message = "Document not found"
    job.completed_at = now
    job.locked_at = None
    if settings.ingestion_dead_letter_enabled:
        job.dead_lettered_at = now


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion.ingest_document_task",
    max_retries=max(0, int(settings.ingestion_max_attempts) - 1),
    soft_time_limit=int(settings.ingestion_task_soft_time_limit_seconds),
    time_limit=int(settings.ingestion_task_time_limit_seconds),
)
def ingest_document_task(
    self: Task,
    *,
    document_id: str,
    workspace_id: str,
    ingestion_job_id: str,
    deduplication_key: str,
) -> dict:
    global ingestion_retries_total, ingestion_terminal_failures_total

    try:
        job_uuid = uuid.UUID(ingestion_job_id)
        doc_uuid = uuid.UUID(document_id)
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return {"status": "ignored", "reason": "invalid_ids"}

    db = SessionLocal()
    job: IngestionJob | None = None
    document: Document | None = None
    try:
        if settings.sentry_dsn:
            try:
                import sentry_sdk

                sentry_sdk.set_tag("workspace_id", workspace_id)
                sentry_sdk.set_tag("document_id", document_id)
                sentry_sdk.set_tag("ingestion_job_id", ingestion_job_id)
            except Exception as e:
                logging.getLogger(__name__).debug("sentry tags for ingestion task failed: %s", e)

        job = db.scalar(select(IngestionJob).where(IngestionJob.id == job_uuid))
        if not job:
            return {"status": "ignored", "reason": "job_not_found"}
        if job.deduplication_key != deduplication_key:
            return {"status": "ignored", "reason": "deduplication_mismatch"}

        document = db.scalar(select(Document).where(Document.id == doc_uuid))
        if not document:
            _mark_document_missing(job)
            db.add(job)
            db.commit()
            return {"status": "failed", "reason": "document_not_found"}

        if document.workspace_id != workspace_uuid:
            _mark_document_missing(job)
            job.error_message = "Workspace mismatch"
            db.add(job)
            db.commit()
            return {"status": "failed", "reason": "workspace_mismatch"}

        # Idempotency: ignore redelivered tasks for already indexed docs.
        if document.status == "ready":
            now = _utcnow()
            job.status = "ready"
            job.error_message = None
            job.locked_at = None
            job.completed_at = now
            job.retry_after_seconds = None
            db.add(job)
            db.commit()
            return {"status": "already_ready", "chunks_created": 0}

        now = _utcnow()
        job.status = "processing"
        job.locked_at = now
        job.attempts = (job.attempts or 0) + 1
        job.celery_task_id = self.request.id
        job.error_message = None
        job.retry_after_seconds = None
        db.add(job)

        document.status = "processing"
        document.error_message = None
        db.add(document)
        db.flush()

        indexer = DocumentIndexingService(db, get_storage_service())
        chunks_created = indexer.run(document)

        done_at = _utcnow()
        job.status = "ready"
        job.error_message = None
        job.completed_at = done_at
        job.locked_at = None
        job.retry_after_seconds = None
        job.dead_lettered_at = None
        db.add(job)
        db.commit()
        return {"status": "ready", "chunks_created": chunks_created}
    except Exception as exc:
        if not job:
            db.rollback()
            raise

        db.rollback()
        job = db.scalar(select(IngestionJob).where(IngestionJob.id == job.id))
        if not job:
            raise
        if document:
            document = db.scalar(select(Document).where(Document.id == document.id))

        error_text = _truncate_error(exc)
        attempt_number = int(job.attempts or 1)
        max_attempts = int(settings.ingestion_max_attempts)
        should_retry = attempt_number < max_attempts

        now = _utcnow()
        job.error_message = error_text
        job.locked_at = None
        job.celery_task_id = self.request.id

        if should_retry:
            delay = _retry_delay_seconds(attempt_number)
            job.status = "retrying"
            job.retry_after_seconds = delay
            job.last_retry_at = now
            job.available_at = now + timedelta(seconds=delay)
            db.add(job)
            if document:
                document.status = "retrying"
                document.error_message = error_text
                db.add(document)
            db.commit()
            logger.warning(
                "ingestion retry scheduled document_id=%s workspace_id=%s attempt=%s/%s countdown=%ss task_id=%s error=%s",
                job.document_id,
                job.workspace_id,
                attempt_number,
                max_attempts,
                delay,
                self.request.id,
                error_text,
            )
            ingestion_retries_total += 1
            raise self.retry(exc=exc, countdown=delay)  # noqa: B904

        ingestion_terminal_failures_total += 1
        job.status = "failed"
        job.completed_at = now
        job.retry_after_seconds = None
        if settings.ingestion_dead_letter_enabled:
            job.dead_lettered_at = now
        db.add(job)
        if document:
            document.status = "failed"
            document.error_message = error_text
            db.add(document)
        write_audit_log(
            db,
            event_type="ingestion.failed",
            workspace_id=job.workspace_id,
            user_id=None,
            target_type="document",
            target_id=str(job.document_id),
            metadata={"job_id": str(job.id), "error": error_text, "attempts": attempt_number},
        )
        db.commit()
        logger.warning(
            "ingestion failed (terminal) document_id=%s workspace_id=%s attempt=%s/%s task_id=%s error=%s",
            job.document_id,
            job.workspace_id,
            attempt_number,
            max_attempts,
            self.request.id,
            error_text,
        )
        return {"status": "failed", "error": error_text}
    finally:
        db.close()


@celery_app.task(name="app.tasks.ingestion.reindex_workspace_embeddings_task")
def reindex_workspace_embeddings_task(*, workspace_id: str) -> dict:
    """Backfill embedding_vector for chunks missing vectors (legacy data)."""
    db = SessionLocal()
    try:
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return {"status": "ignored", "updated": 0}
    try:
        n = reindex_null_embeddings_for_workspace(db, workspace_id=ws_uuid)
        return {"status": "ok", "updated": n}
    except Exception as exc:
        return {"status": "failed", "error": _truncate_error(exc)}
    finally:
        db.close()
