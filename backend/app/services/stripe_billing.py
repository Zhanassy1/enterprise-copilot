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
from app.services.usage_metering import PLAN_LIMITS, get_or_create_quota

logger = logging.getLogger(__name__)


def _stripe_on() -> bool:
    return bool((settings.stripe_secret_key or "").strip())


def init_stripe() -> None:
    if _stripe_on():
        stripe.api_key = settings.stripe_secret_key


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
) -> str:
    init_stripe()
    price = (settings.stripe_price_id or "").strip()
    if not price:
        raise RuntimeError("stripe_price_not_configured")
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


def _apply_pro_plan(q: WorkspaceQuota) -> None:
    slug = "pro"
    d = PLAN_LIMITS.get(slug, PLAN_LIMITS["free"])
    q.plan_slug = slug
    q.monthly_request_limit = int(d["monthly_request_limit"] or 0)
    q.monthly_token_limit = int(d["monthly_token_limit"] or 0)
    q.monthly_upload_bytes_limit = int(d["monthly_upload_bytes_limit"] or 0)
    cap = d.get("max_documents")
    q.max_documents = int(cap) if cap is not None else None


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
        q.subscription_status = "active"
        q.grace_ends_at = None
        _apply_pro_plan(q)
        if sub:
            try:
                s = stripe.Subscription.retrieve(str(sub))
                cpe = getattr(s, "current_period_end", None)
                if cpe:
                    q.current_period_end = datetime.fromtimestamp(int(cpe), tz=UTC)
            except Exception as ex:
                logger.warning("subscription retrieve failed: %s", ex)
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
        q.subscription_status = "active"
        q.grace_ends_at = None
        if sub:
            q.stripe_subscription_id = str(sub)
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
        q.grace_ends_at = None
        q.plan_slug = "free"
        d = PLAN_LIMITS["free"]
        q.monthly_request_limit = int(d["monthly_request_limit"] or 0)
        q.monthly_token_limit = int(d["monthly_token_limit"] or 0)
        q.monthly_upload_bytes_limit = int(d["monthly_upload_bytes_limit"] or 0)
        cap = d.get("max_documents")
        q.max_documents = int(cap) if cap is not None else None
        _ledger_append(db, workspace_id=wid, external_id=eid, event_type=et, meta={"subscription": sub.get("id")})
        return
