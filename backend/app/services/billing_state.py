"""Subscription / grace-period checks for mutating workspace operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.usage_metering import get_or_create_quota


def assert_workspace_billing_allows_writes(db: Session, workspace_id: uuid.UUID) -> None:
    """
    Block writes when a Stripe-backed workspace is past_due after grace, or unpaid canceled state
    that still maps to a paid plan (webhook should downgrade plan_slug; this is a safety net).
    """
    q = get_or_create_quota(db, workspace_id)
    if not (q.stripe_subscription_id or "").strip():
        return
    status = (q.subscription_status or "").lower().strip()
    if status in ("", "active", "trialing"):
        return
    if status == "past_due":
        now = datetime.now(UTC)
        if q.grace_ends_at and q.grace_ends_at > now:
            return
        raise HTTPException(
            status_code=402,
            detail="Subscription past due; update payment in billing settings",
        )
    if status in ("canceled", "unpaid", "incomplete_expired"):
        slug = (q.plan_slug or "free").lower()
        if slug != "free":
            raise HTTPException(
                status_code=402,
                detail="Subscription inactive; renew or choose a plan",
            )
        return
    return
