"""Unit tests for Stripe invoice listing (mocked)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.stripe_billing import list_customer_invoices


@pytest.fixture
def workspace_id() -> uuid.UUID:
    return uuid.uuid4()


@patch("app.services.stripe_billing.stripe.Invoice.list")
def test_list_customer_invoices_empty_without_customer(
    mock_list: MagicMock,
    workspace_id: uuid.UUID,
) -> None:
    db = MagicMock()
    q = MagicMock()
    q.stripe_customer_id = None
    with patch("app.services.stripe_billing.get_or_create_quota", return_value=q):
        with patch("app.services.stripe_billing._stripe_on", return_value=True):
            with patch("app.services.stripe_billing.init_stripe"):
                rows = list_customer_invoices(db, workspace_id=workspace_id, limit=10)
    assert rows == []
    mock_list.assert_not_called()


@patch("app.services.stripe_billing.stripe.Invoice.list")
def test_list_customer_invoices_maps_rows(mock_list: MagicMock, workspace_id: uuid.UUID) -> None:
    inv = MagicMock()
    inv.to_dict.return_value = {
        "id": "in_1",
        "number": "2026-0001",
        "status": "paid",
        "amount_due": 0,
        "amount_paid": 1000,
        "currency": "usd",
        "created": 1710000000,
        "hosted_invoice_url": "https://pay.stripe.com/invoice/test",
        "invoice_pdf": "https://pay.stripe.com/invoice/test/pdf",
    }
    mock_list.return_value = MagicMock(data=[inv])
    q = MagicMock()
    q.stripe_customer_id = "cus_123"
    db = MagicMock()
    with patch("app.services.stripe_billing.get_or_create_quota", return_value=q):
        with patch("app.services.stripe_billing._stripe_on", return_value=True):
            with patch("app.services.stripe_billing.init_stripe"):
                rows = list_customer_invoices(db, workspace_id=workspace_id, limit=10)
    assert len(rows) == 1
    assert rows[0]["id"] == "in_1"
    assert rows[0]["amount_paid"] == 1000
    assert rows[0]["invoice_pdf"] == "https://pay.stripe.com/invoice/test/pdf"
    mock_list.assert_called_once()
