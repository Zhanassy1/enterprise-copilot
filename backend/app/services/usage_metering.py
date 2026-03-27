from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing import UsageEvent, WorkspaceQuota

EVENT_SEARCH_REQUEST = "search_request"
EVENT_CHAT_MESSAGE = "chat_message"
EVENT_DOCUMENT_UPLOAD = "document_upload"
EVENT_TOKENS = "llm_tokens"
EVENT_UPLOAD_BYTES = "document_upload_bytes"


def month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    dt = now or datetime.now(timezone.utc)
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def estimate_tokens(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(cleaned))
    except Exception:
        return max(1, int(math.ceil(len(cleaned.split()) * 1.3)))


def get_or_create_quota(db: Session, workspace_id: uuid.UUID) -> WorkspaceQuota:
    quota = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == workspace_id))
    if quota:
        return quota
    quota = WorkspaceQuota(
        workspace_id=workspace_id,
        monthly_request_limit=20000,
        monthly_token_limit=20_000_000,
        monthly_upload_bytes_limit=1_073_741_824,
    )
    db.add(quota)
    db.flush()
    return quota


def _sum_events(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    event_types: tuple[str, ...],
    unit: str,
    from_dt: datetime,
    to_dt: datetime,
) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.workspace_id == workspace_id,
            UsageEvent.event_type.in_(event_types),
            UsageEvent.unit == unit,
            UsageEvent.created_at >= from_dt,
            UsageEvent.created_at < to_dt,
        )
    )
    return int(value or 0)


def assert_quota(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    request_increment: int = 0,
    token_increment: int = 0,
    upload_bytes_increment: int = 0,
) -> None:
    quota = get_or_create_quota(db, workspace_id)
    start, end = month_window()

    if request_increment > 0:
        current_requests = _sum_events(
            db,
            workspace_id=workspace_id,
            event_types=(EVENT_SEARCH_REQUEST, EVENT_CHAT_MESSAGE, EVENT_DOCUMENT_UPLOAD),
            unit="count",
            from_dt=start,
            to_dt=end,
        )
        if current_requests + int(request_increment) > int(quota.monthly_request_limit):
            raise HTTPException(status_code=429, detail="Workspace monthly request quota exceeded")

    if token_increment > 0:
        current_tokens = _sum_events(
            db,
            workspace_id=workspace_id,
            event_types=(EVENT_TOKENS,),
            unit="tokens",
            from_dt=start,
            to_dt=end,
        )
        if current_tokens + int(token_increment) > int(quota.monthly_token_limit):
            raise HTTPException(status_code=429, detail="Workspace monthly token quota exceeded")

    if upload_bytes_increment > 0:
        current_bytes = _sum_events(
            db,
            workspace_id=workspace_id,
            event_types=(EVENT_UPLOAD_BYTES,),
            unit="bytes",
            from_dt=start,
            to_dt=end,
        )
        if current_bytes + int(upload_bytes_increment) > int(quota.monthly_upload_bytes_limit):
            raise HTTPException(status_code=429, detail="Workspace monthly upload quota exceeded")


def record_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: str,
    quantity: int,
    unit: str = "count",
    metadata: dict[str, Any] | None = None,
) -> UsageEvent:
    row = UsageEvent(
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=event_type,
        quantity=max(0, int(quantity)),
        unit=unit,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(row)
    return row
