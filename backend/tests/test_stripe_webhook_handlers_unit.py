"""Unit tests for Stripe webhook handlers (mocked DB)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.stripe_billing import handle_stripe_event


def test_customer_subscription_updated_applies_status() -> None:
    wid = uuid.uuid4()
    q = MagicMock()
    q.stripe_subscription_id = None
    db = MagicMock()
    with patch("app.services.stripe_billing.init_stripe"):
        with patch("app.services.stripe_billing.get_or_create_quota", return_value=q):
            with patch("app.services.stripe_billing._ledger_append"):
                handle_stripe_event(
                    db,
                    {
                        "type": "customer.subscription.updated",
                        "id": "evt_test",
                        "data": {
                            "object": {
                                "id": "sub_test",
                                "metadata": {"workspace_id": str(wid)},
                                "status": "trialing",
                                "customer": "cus_test",
                                "current_period_end": 1710000000,
                                "trial_end": 1710086400,
                            }
                        },
                    },
                )
    assert q.subscription_status == "trialing"
    assert q.stripe_customer_id == "cus_test"
    assert q.grace_ends_at is None
