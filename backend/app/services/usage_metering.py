from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing import UsageEvent, WorkspaceQuota
from app.models.document import Document

logger = logging.getLogger("app.usage")

# Single source of truth for plan defaults (DB row may diverge after admin/billing updates).
PLAN_DOCUMENT_CAP: dict[str, int | None] = {
    "free": 50,
    "pro": 10_000,
    "team": None,
}

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "monthly_request_limit": 2_000,
        "monthly_token_limit": 2_000_000,
        "monthly_upload_bytes_limit": 536_870_912,  # 512 MiB
        "monthly_rerank_limit": 2_000,
        "max_documents": 50,
        "max_concurrent_ingestion_jobs": 2,
        "max_pdf_pages": 150,
    },
    "pro": {
        "monthly_request_limit": 50_000,
        "monthly_token_limit": 20_000_000,
        "monthly_upload_bytes_limit": 5_368_709_120,  # 5 GiB
        "monthly_rerank_limit": 50_000,
        "max_documents": 10_000,
        "max_concurrent_ingestion_jobs": 8,
        "max_pdf_pages": 2000,
    },
    "team": {
        "monthly_request_limit": 500_000,
        "monthly_token_limit": 200_000_000,
        "monthly_upload_bytes_limit": 53_687_091_200,  # 50 GiB
        "monthly_rerank_limit": 500_000,
        "max_documents": None,
        "max_concurrent_ingestion_jobs": 32,
        "max_pdf_pages": None,
    },
}

EVENT_SEARCH_REQUEST = "search_request"
EVENT_CHAT_MESSAGE = "chat_message"
EVENT_DOCUMENT_UPLOAD = "document_upload"
EVENT_TOKENS = "llm_tokens"
EVENT_UPLOAD_BYTES = "document_upload_bytes"
EVENT_RERANK = "rerank_pass"


def plan_rate_multiplier(plan_slug: str) -> float:
    """Scale global HTTP rate limits by billing plan (best-effort; monthly quotas remain authoritative)."""
    return {"free": 0.75, "pro": 1.0, "team": 2.0}.get((plan_slug or "free").lower(), 1.0)


def effective_rate_limits_for_plan(plan_slug: str) -> dict[str, int]:
    """HTTP rate limits from settings × plan multiplier (used by API middleware)."""
    from app.core.config import settings

    m = plan_rate_multiplier(plan_slug)
    return {
        "per_user": max(10, int(settings.rate_limit_per_user_per_minute * m)),
        "per_ip": max(10, int(settings.rate_limit_per_ip_per_minute * m)),
        "upload_user": max(3, int(settings.rate_limit_upload_per_user_per_minute * m)),
        "auth_ip": max(3, int(settings.rate_limit_auth_per_ip_per_minute * m)),
        "rag_user": max(5, int(settings.rate_limit_rag_per_user_per_minute * m)),
    }


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
    except Exception as e:
        logger.debug("tiktoken unavailable, word-based token estimate: %s", e)
        return max(1, int(math.ceil(len(cleaned.split()) * 1.3)))


def _defaults_for_plan(plan_slug: str) -> dict[str, int | None]:
    slug = (plan_slug or "free").lower()
    return dict(PLAN_LIMITS.get(slug, PLAN_LIMITS["free"]))


def get_or_create_quota(db: Session, workspace_id: uuid.UUID) -> WorkspaceQuota:
    quota = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == workspace_id))
    if quota:
        return quota
    plan = "free"
    d = _defaults_for_plan(plan)
    cap = d.get("max_documents")
    if cap is None:
        cap = PLAN_DOCUMENT_CAP.get(plan, 50)
    quota = WorkspaceQuota(
        workspace_id=workspace_id,
        monthly_request_limit=int(d["monthly_request_limit"] or 0),
        monthly_token_limit=int(d["monthly_token_limit"] or 0),
        monthly_upload_bytes_limit=int(d["monthly_upload_bytes_limit"] or 0),
        plan_slug=plan,
        max_documents=cap,
    )
    db.add(quota)
    db.flush()
    return quota


def _effective_document_cap(quota: WorkspaceQuota) -> int | None:
    if quota.max_documents is not None:
        return int(quota.max_documents)
    slug = (quota.plan_slug or "free").lower()
    cap = PLAN_DOCUMENT_CAP.get(slug, PLAN_DOCUMENT_CAP["free"])
    if cap is not None:
        return int(cap)
    return _defaults_for_plan(slug).get("max_documents")


def max_concurrent_ingestion_jobs_for_workspace(db: Session, workspace_id: uuid.UUID) -> int:
    q = get_or_create_quota(db, workspace_id)
    n = _defaults_for_plan(q.plan_slug or "free").get("max_concurrent_ingestion_jobs")
    return int(n or 2)


def max_pdf_pages_for_workspace(db: Session, workspace_id: uuid.UUID) -> int | None:
    q = get_or_create_quota(db, workspace_id)
    return _defaults_for_plan(q.plan_slug or "free").get("max_pdf_pages")


def _log_quota_violation(workspace_id: uuid.UUID, reason: str) -> None:
    """Structured log for operators (avoid extra DB connection on hot path)."""
    logger.warning(
        json.dumps(
            {"event": "quota.violation", "workspace_id": str(workspace_id), "reason": reason},
            ensure_ascii=False,
        )
    )


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


def _audit_quota_denied(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    reason: str,
) -> None:
    try:
        from app.services.audit import write_audit_log

        write_audit_log(
            db,
            event_type="quota.denied",
            workspace_id=workspace_id,
            user_id=user_id,
            target_type="workspace",
            target_id=str(workspace_id),
            metadata={"reason": reason},
        )
        db.flush()
    except Exception as e:
        logger.warning("audit log for quota.denied failed: %s", e)


def assert_quota(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    request_increment: int = 0,
    token_increment: int = 0,
    upload_bytes_increment: int = 0,
    rerank_increment: int = 0,
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
            _log_quota_violation(workspace_id, "monthly_requests")
            _audit_quota_denied(db, workspace_id=workspace_id, user_id=user_id, reason="monthly_requests")
            raise HTTPException(status_code=429, detail="Workspace monthly request quota exceeded")

    if rerank_increment > 0:
        slug = (quota.plan_slug or "free").lower()
        cap = _defaults_for_plan(slug).get("monthly_rerank_limit")
        if cap is not None:
            current_rr = _sum_events(
                db,
                workspace_id=workspace_id,
                event_types=(EVENT_RERANK,),
                unit="count",
                from_dt=start,
                to_dt=end,
            )
            if current_rr + int(rerank_increment) > int(cap):
                _log_quota_violation(workspace_id, "monthly_rerank")
                _audit_quota_denied(db, workspace_id=workspace_id, user_id=user_id, reason="monthly_rerank")
                raise HTTPException(status_code=429, detail="Workspace monthly rerank quota exceeded")

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
            _log_quota_violation(workspace_id, "monthly_tokens")
            _audit_quota_denied(db, workspace_id=workspace_id, user_id=user_id, reason="monthly_tokens")
            raise HTTPException(status_code=429, detail="Workspace monthly token quota exceeded")

    if upload_bytes_increment > 0:
        cap_docs = _effective_document_cap(quota)
        if cap_docs is not None:
            n = db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
            )
            if int(n or 0) >= int(cap_docs):
                _log_quota_violation(workspace_id, "document_cap")
                _audit_quota_denied(db, workspace_id=workspace_id, user_id=user_id, reason="document_cap")
                raise HTTPException(status_code=403, detail="Workspace document limit reached for this plan")
        current_bytes = _sum_events(
            db,
            workspace_id=workspace_id,
            event_types=(EVENT_UPLOAD_BYTES,),
            unit="bytes",
            from_dt=start,
            to_dt=end,
        )
        if current_bytes + int(upload_bytes_increment) > int(quota.monthly_upload_bytes_limit):
            _log_quota_violation(workspace_id, "monthly_upload_bytes")
            _audit_quota_denied(db, workspace_id=workspace_id, user_id=user_id, reason="monthly_upload_bytes")
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
