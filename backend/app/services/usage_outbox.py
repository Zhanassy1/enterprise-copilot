"""Transactional outbox for upload metering; projects into usage_events idempotently."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.billing import UsageEvent, UsageOutbox
from app.services.usage_metering import (
    EVENT_DOCUMENT_UPLOAD,
    EVENT_UPLOAD_BYTES,
)

logger = logging.getLogger("app.usage_outbox")

OUTBOX_PENDING = "pending"
OUTBOX_SENT = "sent"
OUTBOX_CANCELLED = "cancelled"


def upload_metering_idempotency_key(document_id: uuid.UUID, suffix: str) -> str:
    return f"upload:{document_id}:{suffix}"


def enqueue_upload_metering_outbox(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    size_bytes: int,
) -> None:
    """Insert two pending outbox rows; caller commits in the same transaction as documents/ingestion_jobs."""
    count_key = upload_metering_idempotency_key(document_id, "document_upload")
    bytes_key = upload_metering_idempotency_key(document_id, "document_upload_bytes")
    db.add(
        UsageOutbox(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            user_id=user_id,
            event_type=EVENT_DOCUMENT_UPLOAD,
            quantity=1,
            unit="count",
            metadata_json=json.dumps({"document_id": str(document_id), "filename": filename}, ensure_ascii=False),
            idempotency_key=count_key,
            status=OUTBOX_PENDING,
        )
    )
    db.add(
        UsageOutbox(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            user_id=user_id,
            event_type=EVENT_UPLOAD_BYTES,
            quantity=max(0, int(size_bytes)),
            unit="bytes",
            metadata_json=json.dumps({"document_id": str(document_id)}, ensure_ascii=False),
            idempotency_key=bytes_key,
            status=OUTBOX_PENDING,
        )
    )


def cancel_pending_upload_outbox_for_document(db: Session, *, document_id: uuid.UUID) -> int:
    """Mark pending outbox rows cancelled (e.g. Celery enqueue failed). Returns rowcount."""
    res = db.execute(
        update(UsageOutbox)
        .where(UsageOutbox.document_id == document_id, UsageOutbox.status == OUTBOX_PENDING)
        .values(status=OUTBOX_CANCELLED)
    )
    return int(res.rowcount or 0)


def delete_upload_usage_events_for_document(db: Session, *, document_id: uuid.UUID) -> int:
    """Remove ``usage_events`` rows for this upload (same idempotency keys as ``_record_upload_events``). Used when Celery enqueue fails after commit."""
    keys = (
        upload_metering_idempotency_key(document_id, "document_upload"),
        upload_metering_idempotency_key(document_id, "document_upload_bytes"),
    )
    res = db.execute(delete(UsageEvent).where(UsageEvent.idempotency_key.in_(keys)))
    return int(res.rowcount or 0)


def _project_row_to_usage(db: Session, row: UsageOutbox, now: datetime) -> None:
    ins = (
        pg_insert(UsageEvent)
        .values(
            id=uuid.uuid4(),
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            event_type=row.event_type,
            quantity=max(0, int(row.quantity)),
            unit=row.unit,
            metadata_json=row.metadata_json,
            idempotency_key=row.idempotency_key,
        )
        .on_conflict_do_nothing(constraint="uq_usage_events_idempotency_key")
    )
    db.execute(ins)
    row.status = OUTBOX_SENT
    row.sent_at = now
    db.add(row)


def process_metering_outbox_for_document(db: Session, *, document_id: uuid.UUID) -> dict[str, Any]:
    """Process pending outbox rows for one document (HTTP fast path after upload)."""
    now = datetime.now(UTC)
    stmt = (
        select(UsageOutbox)
        .where(
            UsageOutbox.document_id == document_id,
            UsageOutbox.status == OUTBOX_PENDING,
        )
        .order_by(UsageOutbox.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    rows = list(db.scalars(stmt).all())
    processed = 0
    for row in rows:
        _project_row_to_usage(db, row, now)
        processed += 1
    if processed:
        db.commit()
    else:
        db.rollback()
    return {"document_id": str(document_id), "processed": processed}


def process_usage_outbox_batch(db: Session, *, limit: int = 50) -> dict[str, Any]:
    """Claim pending rows globally; used by Celery and backlog drain."""
    now = datetime.now(UTC)
    stmt = (
        select(UsageOutbox)
        .where(UsageOutbox.status == OUTBOX_PENDING)
        .order_by(UsageOutbox.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list(db.scalars(stmt).all())
    processed = 0
    oldest_pending_age_sec: float | None = None
    for row in rows:
        _project_row_to_usage(db, row, now)
        processed += 1
    if processed:
        db.commit()
    else:
        db.rollback()
    # Observability: age of oldest still-pending row (after this batch)
    oldest = db.scalar(
        select(UsageOutbox.created_at)
        .where(UsageOutbox.status == OUTBOX_PENDING)
        .order_by(UsageOutbox.created_at.asc())
        .limit(1)
    )
    if oldest:
        oldest_pending_age_sec = max(0.0, (now - oldest).total_seconds())
    if oldest_pending_age_sec is not None and oldest_pending_age_sec > 300:
        logger.warning("usage_outbox backlog: oldest pending age %.0fs", oldest_pending_age_sec)
    return {
        "processed": processed,
        "claimed": len(rows),
        "oldest_pending_age_seconds": oldest_pending_age_sec,
    }
