"""Stripe Checkout, Customer Portal, and webhook side-effects."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.billing import BillingLedgerEntry, WorkspaceQuota
from app.services.usage_metering import apply_plan_limits_to_quota, get_or_create_quota

logger = logging.getLogger(__name__)


def _stripe_on() -> bool:
    return bool((settings.stripe_secret_key or "").strip())


def init_stripe() -> None:
    if _stripe_on():
        stripe.api_key = settings.stripe_secret_key


def _stripe_price_id_pro_resolved() -> str:
    return (settings.stripe_price_id_pro or settings.stripe_price_id or "").strip()


def stripe_price_id_for_checkout(plan_slug: str) -> str:
    """Resolve Stripe Price id for Checkout from settings (pro vs team)."""
    s = (plan_slug or "pro").lower().strip()
    if s == "team":
        tid = (settings.stripe_price_id_team or "").strip()
        if not tid:
            raise RuntimeError("stripe_team_price_not_configured")
        return tid
    pid = _stripe_price_id_pro_resolved()
    if not pid:
        raise RuntimeError("stripe_price_not_configured")
    return pid


def plan_slug_from_stripe_price_id(price_id: str | None) -> str:
    """Map a recurring Price id to catalog plan_slug (defaults to pro)."""
    pid = (price_id or "").strip()
    if not pid:
        return "pro"
    team = (settings.stripe_price_id_team or "").strip()
    pro = _stripe_price_id_pro_resolved()
    legacy = (settings.stripe_price_id or "").strip()
    if team and pid == team:
        return "team"
    if pro and pid == pro:
        return "pro"
    if legacy and pid == legacy and not pro:
        return "pro"
    return "pro"


def _subscription_as_dict(sub: Any) -> dict[str, Any]:
    if isinstance(sub, dict):
        return sub
    if hasattr(sub, "to_dict"):
        return sub.to_dict()  # type: ignore[no-any-return]
    return {}


def _primary_recurring_price_id(sub: dict[str, Any]) -> str | None:
    items = sub.get("items")
    if not items:
        return None
    data = items.get("data") if isinstance(items, dict) else None
    if data is None:
        data = getattr(items, "data", None)
    if not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        first = first.to_dict() if hasattr(first, "to_dict") else {}
    price = first.get("price") if isinstance(first, dict) else None
    if isinstance(price, str):
        return price.strip() or None
    if isinstance(price, dict):
        return str(price.get("id") or "").strip() or None
    if price is not None and hasattr(price, "id"):
        return str(getattr(price, "id", "") or "").strip() or None
    return None


def plan_slug_from_stripe_subscription(sub: Any) -> str:
    d = _subscription_as_dict(sub)
    return plan_slug_from_stripe_price_id(_primary_recurring_price_id(d))


def _apply_plan_from_subscription(q: WorkspaceQuota, sub: Any) -> None:
    apply_plan_limits_to_quota(q, plan_slug_from_stripe_subscription(sub))


def ensure_stripe_customer(db: Session, *, workspace_id: uuid.UUID, billing_email: str | None) -> str:
    init_stripe()
    q = get_or_create_quota(db, workspace_id)
    if q.stripe_customer_id:
        return q.stripe_customer_id
    if not _stripe_on():
        raise RuntimeError("stripe_not_configured")
    cust = stripe.Customer.create(
        metadata={"workspace_id": str(workspace_id)},
        email=(billing_email or None),
    )
    q.stripe_customer_id = cust.id
    db.flush()
    return cust.id


def create_checkout_session(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    success_url: str,
    cancel_url: str,
    billing_email: str | None,
    plan_slug: str = "pro",
) -> str:
    init_stripe()
    price = stripe_price_id_for_checkout(plan_slug)
    cid = ensure_stripe_customer(db, workspace_id=workspace_id, billing_email=billing_email)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=cid,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price, "quantity": 1}],
        metadata={"workspace_id": str(workspace_id)},
        subscription_data={"metadata": {"workspace_id": str(workspace_id)}},
    )
    url = session.url
    if not url:
        raise RuntimeError("stripe_no_checkout_url")
    return str(url)


def create_billing_portal_session(db: Session, *, workspace_id: uuid.UUID, return_url: str) -> str:
    init_stripe()
    q = get_or_create_quota(db, workspace_id)
    if not q.stripe_customer_id:
        ensure_stripe_customer(db, workspace_id=workspace_id, billing_email=None)
        q = get_or_create_quota(db, workspace_id)
    cid = q.stripe_customer_id
    if not cid:
        raise RuntimeError("stripe_no_customer")
    ps = stripe.billing_portal.Session.create(customer=cid, return_url=return_url)
    url = ps.url
    if not url:
        raise RuntimeError("stripe_no_portal_url")
    return str(url)


def _ledger_append(db: Session, *, workspace_id: uuid.UUID, external_id: str, event_type: str, meta: dict[str, Any]) -> None:
    existing = db.scalar(select(BillingLedgerEntry).where(BillingLedgerEntry.external_id == external_id))
    if existing:
        return
    db.add(
        BillingLedgerEntry(
            workspace_id=workspace_id,
            external_id=external_id,
            event_type=event_type,
            amount_cents=0,
            currency="USD",
            metadata_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    db.flush()


def _workspace_id_from_meta(meta: dict[str, Any] | None) -> uuid.UUID | None:
    if not meta:
        return None
    raw = meta.get("workspace_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def _apply_stripe_subscription_to_quota(q: WorkspaceQuota, sub: Any) -> None:
    """Sync status, period end, trial end from a Stripe Subscription object or dict."""
    if isinstance(sub, dict):
        status = sub.get("status")
        cpe = sub.get("current_period_end")
        te = sub.get("trial_end")
        sid = sub.get("id")
    else:
        status = getattr(sub, "status", None)
        cpe = getattr(sub, "current_period_end", None)
        te = getattr(sub, "trial_end", None)
        sid = getattr(sub, "id", None)
    if sid:
        q.stripe_subscription_id = str(sid)
    if status:
        q.subscription_status = str(status).lower()
    if cpe:
        q.current_period_end = datetime.fromtimestamp(int(cpe), tz=UTC)
    if te:
        q.trial_ends_at = datetime.fromtimestamp(int(te), tz=UTC)
    else:
        q.trial_ends_at = None


def list_customer_invoices(db: Session, *, workspace_id: uuid.UUID, limit: int) -> list[dict[str, Any]]:
    """Return Stripe invoices for the workspace customer (PDF / hosted URLs)."""
    init_stripe()
    if not _stripe_on():
        raise RuntimeError("stripe_not_configured")
    q = get_or_create_quota(db, workspace_id)
    if not q.stripe_customer_id:
        return []
    lim = max(1, min(int(limit), 100))
    result = stripe.Invoice.list(customer=q.stripe_customer_id, limit=lim)
    rows: list[dict[str, Any]] = []
    for inv in getattr(result, "data", []) or []:
        d = inv.to_dict() if hasattr(inv, "to_dict") else {}
        created = d.get("created")
        rows.append(
            {
                "id": str(d.get("id") or ""),
                "number": d.get("number"),
                "status": d.get("status"),
                "amount_due": int(d.get("amount_due") or 0),
                "amount_paid": int(d.get("amount_paid") or 0),
                "currency": str(d.get("currency") or "usd"),
                "created": datetime.fromtimestamp(int(created), tz=UTC) if created else datetime.now(UTC),
                "hosted_invoice_url": d.get("hosted_invoice_url"),
                "invoice_pdf": d.get("invoice_pdf"),
            }
        )
    return rows


def handle_stripe_event(db: Session, event: dict[str, Any]) -> None:
    init_stripe()
    et = str(event.get("type") or "")
    obj = (event.get("data") or {}).get("object")
    if not isinstance(obj, dict):
        obj = {}
    eid = str(event.get("id") or "")

    if et == "checkout.session.completed":
        meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        wid = _workspace_id_from_meta(meta)
        if not wid:
            logger.warning("checkout.session.completed missing workspace_id metadata")
            return
        q = get_or_create_quota(db, wid)
        cust = obj.get("customer")
        sub = obj.get("subscription")
        if cust:
            q.stripe_customer_id = str(cust)
        if sub:
            q.stripe_subscription_id = str(sub)
        q.grace_ends_at = None
        if sub:
            try:
                s = stripe.Subscription.retrieve(str(sub))
                _apply_stripe_subscription_to_quota(q, s)
                _apply_plan_from_subscription(q, s)
                if (q.subscription_status or "") in ("active", "trialing"):
                    q.grace_ends_at = None
            except Exception as ex:
                logger.warning("subscription retrieve failed: %s", ex)
                q.subscription_status = "active"
                apply_plan_limits_to_quota(q, "pro")
        else:
            q.subscription_status = "active"
            apply_plan_limits_to_quota(q, "pro")
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"session": obj.get("id")})
        return

    if et == "invoice.paid":
        inv = obj
        sub = inv.get("subscription")
        wid = None
        if sub:
            try:
                s = stripe.Subscription.retrieve(str(sub))
                md = getattr(s, "metadata", None)
                meta = md if isinstance(md, dict) else (md.to_dict() if hasattr(md, "to_dict") else {})
                wid = _workspace_id_from_meta(meta)
            except Exception as ex:
                logger.warning("invoice.paid subscription fetch failed: %s", ex)
        cust = inv.get("customer")
        if not wid and cust:
            qrow = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.stripe_customer_id == str(cust)))
            if qrow:
                wid = qrow.workspace_id
        if not wid:
            logger.warning("invoice.paid could not resolve workspace")
            return
        q = get_or_create_quota(db, wid)
        q.grace_ends_at = None
        if sub:
            q.stripe_subscription_id = str(sub)
            try:
                s = stripe.Subscription.retrieve(str(sub))
                _apply_stripe_subscription_to_quota(q, s)
                _apply_plan_from_subscription(q, s)
            except Exception as ex:
                logger.warning("invoice.paid subscription retrieve failed: %s", ex)
                q.subscription_status = "active"
        else:
            q.subscription_status = "active"
        cpe = inv.get("period_end")
        if cpe:
            q.current_period_end = datetime.fromtimestamp(int(cpe), tz=UTC)
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"invoice": inv.get("id")})
        return

    if et == "invoice.payment_failed":
        inv = obj
        sub = inv.get("subscription")
        wid = None
        if sub:
            try:
                s = stripe.Subscription.retrieve(str(sub))
                md = getattr(s, "metadata", None)
                meta = md if isinstance(md, dict) else (md.to_dict() if hasattr(md, "to_dict") else {})
                wid = _workspace_id_from_meta(meta)
            except Exception as ex:
                logger.warning("invoice.payment_failed subscription fetch failed: %s", ex)
        cust = inv.get("customer")
        if not wid and cust:
            qrow = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.stripe_customer_id == str(cust)))
            if qrow:
                wid = qrow.workspace_id
        if not wid:
            return
        q = get_or_create_quota(db, wid)
        q.subscription_status = "past_due"
        days = int(settings.billing_grace_period_days)
        q.grace_ends_at = datetime.now(UTC) + timedelta(days=days)
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"invoice": inv.get("id")})
        return

    if et == "customer.subscription.updated":
        sub = obj
        meta = sub.get("metadata") if isinstance(sub.get("metadata"), dict) else {}
        wid = _workspace_id_from_meta(meta)
        if not wid:
            sid = sub.get("id")
            if sid:
                qrow = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.stripe_subscription_id == str(sid)))
                if qrow:
                    wid = qrow.workspace_id
        if not wid:
            return
        q = get_or_create_quota(db, wid)
        _apply_stripe_subscription_to_quota(q, sub)
        _apply_plan_from_subscription(q, sub)
        st = (q.subscription_status or "").lower()
        if st in ("active", "trialing"):
            q.grace_ends_at = None
        cust = sub.get("customer")
        if cust:
            q.stripe_customer_id = str(cust)
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"subscription": sub.get("id")})
        return

    if et == "customer.subscription.deleted":
        sub = obj
        meta = sub.get("metadata") if isinstance(sub.get("metadata"), dict) else {}
        wid = _workspace_id_from_meta(meta)
        if not wid:
            sid = sub.get("id")
            if sid:
                qrow = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.stripe_subscription_id == str(sid)))
                if qrow:
                    wid = qrow.workspace_id
        if not wid:
            return
        q = get_or_create_quota(db, wid)
        q.stripe_subscription_id = None
        q.subscription_status = "canceled"
        q.current_period_end = None
        q.trial_ends_at = None
        q.grace_ends_at = None
        apply_plan_limits_to_quota(q, "free")
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"subscription": sub.get("id")})
        return
