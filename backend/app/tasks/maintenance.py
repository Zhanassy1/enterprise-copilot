"""Periodic maintenance: retention after soft-delete."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.services.storage import get_storage_service


@celery_app.task(name="app.tasks.maintenance.purge_expired_soft_deleted_documents")
def purge_expired_soft_deleted_documents() -> dict:
    """Remove storage and DB rows for documents soft-deleted past retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(settings.document_retention_days_after_soft_delete))
    db = SessionLocal()
    storage = get_storage_service()
    removed = 0
    try:
        rows = db.scalars(
            select(Document).where(Document.deleted_at.isnot(None), Document.deleted_at < cutoff).limit(500)
        ).all()
        for doc in rows:
            try:
                storage.delete(doc.storage_key)
            except Exception:
                pass
            db.delete(doc)
            removed += 1
        db.commit()
        return {"status": "ok", "removed": removed, "cutoff": cutoff.isoformat()}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "message": str(exc)[:500]}
    finally:
        db.close()

