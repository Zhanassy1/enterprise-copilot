"""Periodic / manual maintenance tasks (retention, cleanup)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.services.storage import get_storage_service

logger = logging.getLogger("app.maintenance")


@celery_app.task(name="maintenance.purge_soft_deleted_documents")
def purge_soft_deleted_documents_task() -> dict:
    """Remove documents soft-deleted longer than retention; deletes blobs then rows (cascade chunks/jobs)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(settings.document_retention_days_after_soft_delete))
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
            try:
                storage.delete(doc.storage_key)
            except Exception as exc:
                logger.warning("storage delete failed for %s: %s", doc.storage_key, exc)
            db.delete(doc)
            removed += 1
        db.commit()
    except Exception as e:
        logger.exception("purge_soft_deleted_documents failed: %s", e)
        db.rollback()
        raise
    finally:
        db.close()
    return {"removed_documents": removed, "cutoff_iso": cutoff.isoformat()}
