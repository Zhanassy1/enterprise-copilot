from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import BillingOwnerAdmin, CurrentUser, DbDep, WorkspaceReadAccess
from app.core.config import settings
from app.models.billing import BillingLedgerEntry
from app.models.document import Document
from app.schemas.billing_api import (
    BillingCheckoutIn,
    BillingInvoiceOut,
    BillingLedgerOut,
    BillingPortalIn,
    BillingUrlOut,
    SubscriptionOut,
    UsageSummaryOut,
)
from app.services.billing_subscription import compute_billing_state, compute_subscription_banner
from app.services.stripe_billing import (
    create_billing_portal_session,
    create_checkout_session,
    list_customer_invoices,
)
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


@router.get("/subscription", response_model=SubscriptionOut)
def billing_subscription(db: DbDep, ws: WorkspaceReadAccess) -> SubscriptionOut:
    quota = get_or_create_quota(db, ws.workspace.id)
    variant, msg, past_compat = compute_subscription_banner(quota)
    state = compute_billing_state(quota)
    return SubscriptionOut(
        plan_slug=quota.plan_slug,
        subscription_status=quota.subscription_status,
        current_period_end=quota.current_period_end,
        trial_ends_at=quota.trial_ends_at,
        grace_ends_at=quota.grace_ends_at,
        billing_state=state,
        renewal_at=quota.current_period_end,
        grace_until=quota.grace_ends_at,
        past_due_banner=past_compat,
        banner_variant=variant,
        banner_message=msg,
    )


@router.get("/invoices", response_model=list[BillingInvoiceOut])
def billing_invoices(
    db: DbDep,
    ws: BillingOwnerAdmin,
    limit: int = Query(default=24, ge=1, le=100),
) -> list[BillingInvoiceOut]:
    try:
        rows = list_customer_invoices(db, workspace_id=ws.workspace.id, limit=limit)
    except RuntimeError as e:
        if str(e) == "stripe_not_configured":
            raise HTTPException(status_code=503, detail="Stripe is not configured") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    return [BillingInvoiceOut(**r) for r in rows]


@router.post("/portal", response_model=BillingUrlOut)
def billing_portal(body: BillingPortalIn, db: DbDep, ws: BillingOwnerAdmin) -> BillingUrlOut:
    try:
        url = create_billing_portal_session(db, workspace_id=ws.workspace.id, return_url=body.return_url)
    except RuntimeError as e:
        code = str(e)
        if code == "stripe_not_configured":
            raise HTTPException(status_code=503, detail="Stripe is not configured") from e
        raise HTTPException(status_code=400, detail=code) from e
    return BillingUrlOut(url=url)


@router.post("/checkout", response_model=BillingUrlOut)
def billing_checkout(
    body: BillingCheckoutIn,
    db: DbDep,
    ws: BillingOwnerAdmin,
    user: CurrentUser,
) -> BillingUrlOut:
    base = settings.app_base_url.rstrip("/")
    success = body.success_url or f"{base}/billing?checkout=success"
    cancel = body.cancel_url or f"{base}/billing?checkout=cancel"
    try:
        url = create_checkout_session(
            db,
            workspace_id=ws.workspace.id,
            success_url=success,
            cancel_url=cancel,
            billing_email=user.email,
            plan_slug=body.plan_slug,
        )
    except RuntimeError as e:
        code = str(e)
        if code == "stripe_not_configured":
            raise HTTPException(status_code=503, detail="Stripe is not configured") from e
        if code == "stripe_price_not_configured":
            raise HTTPException(status_code=503, detail="Stripe price id is not configured") from e
        if code == "stripe_team_price_not_configured":
            raise HTTPException(status_code=503, detail="Stripe Team price id is not configured") from e
        raise HTTPException(status_code=400, detail=code) from e
    return BillingUrlOut(url=url)


@router.get("/usage", response_model=UsageSummaryOut)
def billing_usage(db: DbDep, ws: BillingOwnerAdmin) -> UsageSummaryOut:
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
    ws: BillingOwnerAdmin,
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
