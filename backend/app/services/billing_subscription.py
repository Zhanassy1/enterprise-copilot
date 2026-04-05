"""Subscription API payload: dunning banners aligned with ``billing_state`` 402 rules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from app.models.billing import WorkspaceQuota

BannerVariant = Literal["none", "warning", "critical"]

# UI-facing subscription state; single source for GET /billing/subscription.
BillingState = Literal["free", "active", "trialing", "grace", "past_due", "canceled"]


def compute_billing_state(
    quota: WorkspaceQuota,
    *,
    now: datetime | None = None,
) -> BillingState:
    """
    Derive ``billing_state`` from ``WorkspaceQuota`` (Stripe fields + plan_slug).

    - ``grace``: Stripe status past_due and current time before ``grace_ends_at``.
    - ``free``: no Stripe subscription id (quota-only / never subscribed).
    """
    if now is None:
        now = datetime.now(UTC)
    has_sub = bool((quota.stripe_subscription_id or "").strip())
    if not has_sub:
        return "free"
    status = (quota.subscription_status or "").lower().strip() or "active"
    if status == "past_due":
        if quota.grace_ends_at is not None and quota.grace_ends_at > now:
            return "grace"
        return "past_due"
    if status in ("canceled", "unpaid", "incomplete_expired"):
        return "canceled"
    if status == "trialing":
        return "trialing"
    if status == "active":
        return "active"
    return "active"


def _plan_feature_label(plan_slug: str) -> str:
    s = (plan_slug or "free").lower().strip()
    if s == "pro":
        return "Pro"
    if s == "team":
        return "Team"
    return "плана"


def compute_subscription_banner(
    quota: WorkspaceQuota,
    *,
    now: datetime | None = None,
) -> tuple[BannerVariant, str | None, bool]:
    """
    Returns (banner_variant, banner_message, past_due_banner_compat).

    ``past_due_banner_compat`` is True when any billing alert should show (warning or critical).
    """
    if now is None:
        now = datetime.now(UTC)
    has_stripe = bool((quota.stripe_subscription_id or "").strip())
    plan_slug = (quota.plan_slug or "free").lower()
    status = (quota.subscription_status or "").lower() or None
    in_grace = status == "past_due" and quota.grace_ends_at is not None and quota.grace_ends_at > now
    label = _plan_feature_label(plan_slug)

    if not has_stripe:
        return "none", None, False

    if status == "past_due":
        if in_grace:
            msg = (
                "Проблема с оплатой. Обновите данные карты, чтобы не потерять доступ "
                f"к функциям {label}."
            )
            return "warning", msg, True
        msg = (
            "Срок льготного периода истёк. Обновите карту в настройках биллинга, "
            "чтобы восстановить доступ."
        )
        return "critical", msg, True

    if status in ("canceled", "unpaid", "incomplete_expired") and plan_slug != "free":
        msg = (
            "Подписка неактивна. Оформите подписку или попросите администратора workspace "
            "обновить оплату."
        )
        return "critical", msg, True

    return "none", None, False
