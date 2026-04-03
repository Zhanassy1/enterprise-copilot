import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import DbDep, PlatformAdmin
from app.core.security import create_access_token
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.admin_api import ImpersonateIn, QuotaAdjustIn
from app.schemas.auth import Token
from app.schemas.billing_api import UsageSummaryOut
from app.services.audit import write_audit_log
from app.services.usage_metering import (
    EVENT_CHAT_MESSAGE,
    EVENT_DOCUMENT_UPLOAD,
    EVENT_SEARCH_REQUEST,
    EVENT_TOKENS,
    EVENT_UPLOAD_BYTES,
    PLAN_LIMITS,
    _sum_events,
    get_or_create_quota,
    month_window,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/impersonation/start", response_model=Token)
def admin_impersonation_start(body: ImpersonateIn, db: DbDep, admin: PlatformAdmin) -> Token:
    target = db.scalar(select(User).where(User.id == body.user_id))
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    write_audit_log(
        db,
        event_type="impersonation.start",
        workspace_id=None,
        user_id=admin.id,
        target_type="user",
        target_id=str(target.id),
        metadata={"target_user_id": str(target.id), "admin_email": admin.email},
    )
    db.commit()
    access = create_access_token(str(target.id), expires_minutes=30, extra={"imp": str(admin.id)})
    return Token(access_token=access, refresh_token=None)


@router.get("/workspaces/{workspace_id}/usage", response_model=UsageSummaryOut)
def admin_workspace_usage(workspace_id: uuid.UUID, db: DbDep, _admin: PlatformAdmin) -> UsageSummaryOut:
    ws = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    quota = get_or_create_quota(db, workspace_id)
    start, end = month_window()
    req = _sum_events(
        db,
        workspace_id=workspace_id,
        event_types=(EVENT_SEARCH_REQUEST, EVENT_CHAT_MESSAGE, EVENT_DOCUMENT_UPLOAD),
        unit="count",
        from_dt=start,
        to_dt=end,
    )
    tok = _sum_events(
        db,
        workspace_id=workspace_id,
        event_types=(EVENT_TOKENS,),
        unit="tokens",
        from_dt=start,
        to_dt=end,
    )
    byt = _sum_events(
        db,
        workspace_id=workspace_id,
        event_types=(EVENT_UPLOAD_BYTES,),
        unit="bytes",
        from_dt=start,
        to_dt=end,
    )
    doc_count = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
    )
    return UsageSummaryOut(
        plan_slug=quota.plan_slug,
        monthly_request_limit=int(quota.monthly_request_limit),
        monthly_token_limit=int(quota.monthly_token_limit),
        monthly_upload_bytes_limit=int(quota.monthly_upload_bytes_limit),
        max_documents=int(quota.max_documents) if quota.max_documents is not None else None,
        usage_requests_month=int(req),
        usage_tokens_month=int(tok),
        usage_bytes_month=int(byt),
        document_count=int(doc_count or 0),
    )


@router.post("/workspaces/{workspace_id}/quota")
def admin_quota_adjust(
    workspace_id: uuid.UUID,
    body: QuotaAdjustIn,
    db: DbDep,
    admin: PlatformAdmin,
) -> dict[str, str]:
    ws = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    q = get_or_create_quota(db, workspace_id)
    if body.monthly_request_limit is not None:
        q.monthly_request_limit = int(body.monthly_request_limit)
    if body.monthly_token_limit is not None:
        q.monthly_token_limit = int(body.monthly_token_limit)
    if body.plan_slug is not None:
        slug = body.plan_slug.strip().lower()
        if slug not in PLAN_LIMITS:
            raise HTTPException(status_code=400, detail="Unknown plan_slug")
        q.plan_slug = slug
        d = PLAN_LIMITS[slug]
        if body.monthly_request_limit is None:
            q.monthly_request_limit = int(d["monthly_request_limit"] or 0)
        if body.monthly_token_limit is None:
            q.monthly_token_limit = int(d["monthly_token_limit"] or 0)
        q.monthly_upload_bytes_limit = int(d["monthly_upload_bytes_limit"] or 0)
        cap = d.get("max_documents")
        q.max_documents = int(cap) if cap is not None else None
    if body.extend_grace_days is not None:
        q.grace_ends_at = datetime.now(UTC) + timedelta(days=int(body.extend_grace_days))
    write_audit_log(
        db,
        event_type="admin.quota_adjust",
        workspace_id=workspace_id,
        user_id=admin.id,
        target_type="workspace_quota",
        target_id=str(q.id),
        metadata={
            "monthly_request_limit": body.monthly_request_limit,
            "monthly_token_limit": body.monthly_token_limit,
            "plan_slug": body.plan_slug,
            "extend_grace_days": body.extend_grace_days,
        },
    )
    db.commit()
    return {"ok": "true"}
