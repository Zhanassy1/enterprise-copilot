from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbDep, WorkspaceReadAccess
from app.models.billing import BillingLedgerEntry
from app.models.document import Document
from app.schemas.billing_api import BillingLedgerOut, UsageSummaryOut
from app.services.usage_metering import (
    EVENT_CHAT_MESSAGE,
    EVENT_DOCUMENT_UPLOAD,
    EVENT_SEARCH_REQUEST,
    EVENT_TOKENS,
    EVENT_UPLOAD_BYTES,
    _sum_events,
    get_or_create_quota,
    month_window,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage", response_model=UsageSummaryOut)
def billing_usage(db: DbDep, ws: WorkspaceReadAccess) -> UsageSummaryOut:
    quota = get_or_create_quota(db, ws.workspace.id)
    start, end = month_window()
    req = _sum_events(
        db,
        workspace_id=ws.workspace.id,
        event_types=(EVENT_SEARCH_REQUEST, EVENT_CHAT_MESSAGE, EVENT_DOCUMENT_UPLOAD),
        unit="count",
        from_dt=start,
        to_dt=end,
    )
    tok = _sum_events(
        db,
        workspace_id=ws.workspace.id,
        event_types=(EVENT_TOKENS,),
        unit="tokens",
        from_dt=start,
        to_dt=end,
    )
    byt = _sum_events(
        db,
        workspace_id=ws.workspace.id,
        event_types=(EVENT_UPLOAD_BYTES,),
        unit="bytes",
        from_dt=start,
        to_dt=end,
    )
    doc_count = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.workspace_id == ws.workspace.id, Document.deleted_at.is_(None))
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


@router.get("/ledger", response_model=list[BillingLedgerOut])
def billing_ledger(
    db: DbDep,
    ws: WorkspaceReadAccess,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BillingLedgerOut]:
    rows = db.scalars(
        select(BillingLedgerEntry)
        .where(BillingLedgerEntry.workspace_id == ws.workspace.id)
        .order_by(BillingLedgerEntry.created_at.desc())
        .limit(limit)
    ).all()
    return [
        BillingLedgerOut(
            id=r.id,
            workspace_id=r.workspace_id,
            external_id=r.external_id,
            event_type=r.event_type,
            amount_cents=int(r.amount_cents),
            currency=r.currency,
            created_at=r.created_at,
        )
        for r in rows
    ]
