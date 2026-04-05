"""Unit tests for subscription banner logic (no DB)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from types import SimpleNamespace

import pytest

from app.services.billing_subscription import compute_billing_state, compute_subscription_banner


@pytest.mark.parametrize(
    ("status", "in_grace", "plan", "variant", "has_msg"),
    [
        ("past_due", True, "pro", "warning", True),
        ("past_due", False, "pro", "critical", True),
        ("active", True, "pro", "none", False),
        ("trialing", False, "pro", "none", False),
        ("canceled", False, "pro", "critical", True),
        ("canceled", False, "free", "none", False),
    ],
)
def test_compute_subscription_banner_stripe(
    status: str,
    in_grace: bool,
    plan: str,
    variant: str,
    has_msg: bool,
) -> None:
    now = datetime.now(UTC)
    grace = now + timedelta(days=2) if in_grace else now - timedelta(days=1)
    q = SimpleNamespace(
        stripe_subscription_id="sub_123",
        plan_slug=plan,
        subscription_status=status,
        grace_ends_at=grace if status == "past_due" else None,
    )
    v, msg, compat = compute_subscription_banner(q, now=now)
    assert v == variant
    assert (msg is not None) == has_msg
    assert compat == (variant != "none")


@pytest.mark.parametrize(
    ("sub_id", "status", "grace_future", "expected"),
    [
        (None, "active", True, "free"),
        ("sub_1", "active", False, "active"),
        ("sub_1", "trialing", False, "trialing"),
        ("sub_1", "past_due", True, "grace"),
        ("sub_1", "past_due", False, "past_due"),
        ("sub_1", "canceled", False, "canceled"),
    ],
)
def test_compute_billing_state(
    sub_id: str | None,
    status: str,
    grace_future: bool,
    expected: str,
) -> None:
    now = datetime.now(UTC)
    grace = now + timedelta(days=2) if grace_future else now - timedelta(days=1)
    q = SimpleNamespace(
        stripe_subscription_id=sub_id,
        plan_slug="pro",
        subscription_status=status,
        grace_ends_at=grace if status == "past_due" else None,
    )
    assert compute_billing_state(q, now=now) == expected


def test_compute_subscription_banner_no_stripe() -> None:
    q = SimpleNamespace(
        stripe_subscription_id=None,
        plan_slug="pro",
        subscription_status="past_due",
        grace_ends_at=datetime.now(UTC) + timedelta(days=1),
    )
    v, msg, compat = compute_subscription_banner(q)
    assert v == "none" and msg is None and compat is False
