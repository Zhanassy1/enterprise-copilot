"""Periodic / manual maintenance tasks (retention, cleanup)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.services.storage import StorageService, get_storage_service
from app.services.usage_outbox import process_usage_outbox_batch

logger = logging.getLogger("app.maintenance")


def delete_document_blob_and_row(db: Session, doc: Document, storage: StorageService) -> None:
    """Remove object storage bytes then ORM row (CASCADE removes chunks and ingestion_jobs)."""
    try:
        storage.delete(doc.storage_key)
    except Exception as exc:
        logger.warning("storage delete failed for %s: %s", doc.storage_key, exc)
    db.delete(doc)


@celery_app.task(name="maintenance.purge_soft_deleted_documents")
def purge_soft_deleted_documents_task() -> dict:
    """Remove documents soft-deleted longer than retention; deletes blobs then rows (cascade chunks/jobs)."""
    cutoff = datetime.now(UTC) - timedelta(days=int(settings.document_retention_days_after_soft_delete))
    storage = get_storage_service()
    db = SessionLocal()
    removed = 0
    try:
        rows = list(
            db.scalars(
                select(Document).where(Document.deleted_at.is_not(None), Document.deleted_at < cutoff)
            ).all()
        )
        for doc in rows:
            delete_document_blob_and_row(db, doc, storage)
            removed += 1
        db.commit()
    except Exception as e:
        logger.exception("purge_soft_deleted_documents failed: %s", e)
        db.rollback()
        raise
    finally:
        db.close()
    return {"removed_documents": removed, "cutoff_iso": cutoff.isoformat()}


@celery_app.task(name="maintenance.hard_delete_soft_deleted_document")
def hard_delete_soft_deleted_document_task(*, document_id: str, workspace_id: str) -> dict:
    """Hard-delete one soft-deleted document (storage + row). Used when immediate_hard_delete_after_soft_delete is enabled."""
    try:
        doc_uuid = uuid.UUID(document_id)
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return {"status": "ignored", "reason": "invalid_ids"}

    storage = get_storage_service()
    db = SessionLocal()
    try:
        doc = db.scalar(select(Document).where(Document.id == doc_uuid))
        if not doc:
            return {"status": "ignored", "reason": "document_not_found"}
        if doc.workspace_id != ws_uuid:
            return {"status": "ignored", "reason": "workspace_mismatch"}
        if doc.deleted_at is None:
            return {"status": "ignored", "reason": "not_soft_deleted"}
        delete_document_blob_and_row(db, doc, storage)
        db.commit()
        return {"status": "ok", "document_id": document_id}
    except Exception as e:
        logger.exception("hard_delete_soft_deleted_document failed: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="maintenance.process_usage_outbox")
def process_usage_outbox_task(limit: int = 50) -> dict:
    """Drain pending upload metering outbox into usage_events (idempotent)."""
    db = SessionLocal()
    try:
        return process_usage_outbox_batch(db, limit=limit)
    except Exception as e:
        logger.exception("process_usage_outbox failed: %s", e)
        db.rollback()
        raise
    finally:
        db.close()
