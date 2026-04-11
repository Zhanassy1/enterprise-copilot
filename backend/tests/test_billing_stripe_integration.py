"""Stripe billing flows: checkout, portal, webhooks, grace vs 402 (PostgreSQL + mocked Stripe SDK)."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


@pytest.fixture
def configure_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_integration")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_integration")
    monkeypatch.setattr(settings, "stripe_price_id", "price_pro_legacy")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_pro_legacy")
    monkeypatch.setattr(settings, "stripe_price_id_team", "price_team_test")


def test_billing_checkout_returns_url(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    configure_stripe,
) -> None:
    a = two_workspaces["a"]
    with patch("app.services.stripe_billing.stripe.checkout.Session.create") as m_create:
        m_create.return_value = MagicMock(url="https://checkout.stripe.com/c/pay/cs_test_1")
        with patch("app.services.stripe_billing.stripe.Customer.create") as m_cust:
            m_cust.return_value = MagicMock(id="cus_test_checkout")
            r = client.post(
                "/api/v1/billing/checkout",
                headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
                json={"success_url": "http://localhost:3000/ok", "cancel_url": "http://localhost:3000/cancel", "plan_slug": "pro"},
            )
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://checkout.stripe.com/")


def test_billing_checkout_team_503_without_team_price(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_integration")
    monkeypatch.setattr(settings, "stripe_price_id", "price_pro_legacy")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_pro_legacy")
    monkeypatch.setattr(settings, "stripe_price_id_team", "")
    a = two_workspaces["a"]
    r = client.post(
        "/api/v1/billing/checkout",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        json={"plan_slug": "team"},
    )
    assert r.status_code == 503


def test_billing_portal_returns_url(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    configure_stripe,
) -> None:
    from app.db.session import SessionLocal
    from app.services.usage_metering import get_or_create_quota

    a = two_workspaces["a"]
    wid = uuid.UUID(a["ws"])
    db = SessionLocal()
    try:
        q = get_or_create_quota(db, wid)
        q.stripe_customer_id = "cus_portal_test"
        db.commit()
    finally:
        db.close()

    with patch("app.services.stripe_billing.stripe.billing_portal.Session.create") as m_portal:
        m_portal.return_value = MagicMock(url="https://billing.stripe.com/session/test")
        r = client.post(
            "/api/v1/billing/portal",
            headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
            json={"return_url": "http://localhost:3000/w/ws/billing"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://billing.stripe.com/")


def _fake_subscription_dict(*, workspace_id: str, price_id: str = "price_team_test") -> dict:
    return {
        "id": "sub_integration_1",
        "status": "active",
        "customer": "cus_evt",
        "metadata": {"workspace_id": workspace_id},
        "current_period_end": 1890000000,
        "trial_end": None,
        "items": {
            "data": [
                {
                    "price": {"id": price_id},
                }
            ]
        },
    }


def test_stripe_webhook_checkout_completed_updates_quota(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    configure_stripe,
) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.billing import WorkspaceQuota

    a = two_workspaces["a"]
    wid = a["ws"]
    event_dict = {
        "id": "evt_checkout_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "customer": "cus_evt",
                "subscription": "sub_integration_1",
                "metadata": {"workspace_id": wid},
            }
        },
    }
    fake_sub = _fake_subscription_dict(workspace_id=wid, price_id="price_team_test")

    mock_event = MagicMock()
    mock_event.to_dict.return_value = event_dict

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        with patch("app.services.stripe_billing.stripe.Subscription.retrieve", return_value=fake_sub):
            r = client.post(
                "/api/v1/billing/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        q = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == uuid.UUID(wid)))
        assert q is not None
        assert q.stripe_customer_id == "cus_evt"
        assert q.stripe_subscription_id == "sub_integration_1"
        assert q.plan_slug == "team"
        assert q.monthly_request_limit >= 100_000
    finally:
        db.close()


def test_stripe_webhook_payment_failed_sets_grace(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    configure_stripe,
) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.billing import WorkspaceQuota

    b = two_workspaces["b"]
    wid = b["ws"]
    fake_sub = _fake_subscription_dict(workspace_id=wid)
    event_dict = {
        "id": "evt_inv_failed",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_1",
                "customer": "cus_evt",
                "subscription": "sub_integration_1",
            }
        },
    }
    mock_event = MagicMock()
    mock_event.to_dict.return_value = event_dict

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        with patch("app.services.stripe_billing.stripe.Subscription.retrieve", return_value=fake_sub):
            r = client.post(
                "/api/v1/billing/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        q = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == uuid.UUID(wid)))
        assert q is not None
        assert q.subscription_status == "past_due"
        assert q.grace_ends_at is not None
        assert q.grace_ends_at > datetime.now(UTC)
    finally:
        db.close()


def test_stripe_webhook_subscription_deleted_downgrades_free(
    client: TestClient,
    two_workspaces: dict[str, dict[str, str]],
    configure_stripe,
) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.billing import WorkspaceQuota

    b = two_workspaces["b"]
    wid = b["ws"]
    event_dict = {
        "id": "evt_del",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_integration_1",
                "customer": "cus_evt",
                "metadata": {"workspace_id": wid},
            }
        },
    }
    mock_event = MagicMock()
    mock_event.to_dict.return_value = event_dict

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        r = client.post(
            "/api/v1/billing/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        q = db.scalar(select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == uuid.UUID(wid)))
        assert q is not None
        assert q.plan_slug == "free"
        assert q.stripe_subscription_id is None
        assert q.subscription_status == "canceled"
    finally:
        db.close()


def test_past_due_in_grace_allows_writes(
    two_workspaces: dict[str, dict[str, str]],
) -> None:
    from app.db.session import SessionLocal
    from app.services.billing_state import assert_workspace_billing_allows_writes
    from app.services.usage_metering import get_or_create_quota

    a = two_workspaces["a"]
    wid = uuid.UUID(a["ws"])
    db = SessionLocal()
    try:
        q = get_or_create_quota(db, wid)
        q.stripe_subscription_id = "sub_x"
        q.subscription_status = "past_due"
        q.grace_ends_at = datetime.now(UTC) + timedelta(days=2)
        db.commit()
        assert_workspace_billing_allows_writes(db, wid)
    finally:
        db.close()


def test_past_due_after_grace_blocks_writes(
    two_workspaces: dict[str, dict[str, str]],
) -> None:
    from app.db.session import SessionLocal
    from app.services.billing_state import assert_workspace_billing_allows_writes
    from app.services.usage_metering import get_or_create_quota

    a = two_workspaces["a"]
    wid = uuid.UUID(a["ws"])
    db = SessionLocal()
    try:
        q = get_or_create_quota(db, wid)
        q.stripe_subscription_id = "sub_x"
        q.subscription_status = "past_due"
        q.grace_ends_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        with pytest.raises(HTTPException) as ei:
            assert_workspace_billing_allows_writes(db, wid)
        assert ei.value.status_code == 402
    finally:
        db.close()
