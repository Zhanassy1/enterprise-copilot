import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UsageSummaryOut(BaseModel):
    plan_slug: str
    monthly_request_limit: int
    monthly_token_limit: int
    monthly_upload_bytes_limit: int
    max_documents: int | None
    usage_requests_month: int
    usage_tokens_month: int
    usage_bytes_month: int
    document_count: int


class SubscriptionOut(BaseModel):
    plan_slug: str
    subscription_status: str | None
    current_period_end: datetime | None
    trial_ends_at: datetime | None
    grace_ends_at: datetime | None
    billing_state: Literal["free", "active", "trialing", "grace", "past_due", "canceled"]
    renewal_at: datetime | None = Field(
        default=None,
        description="Alias for current_period_end (next renewal boundary in UTC).",
    )
    grace_until: datetime | None = Field(
        default=None,
        description="Alias for grace_ends_at (end of dunning grace window, UTC).",
    )
    past_due_banner: bool = Field(
        description="True when a billing alert should show (warning or critical); prefer banner_variant.",
    )
    banner_variant: Literal["none", "warning", "critical"]
    banner_message: str | None


class BillingInvoiceOut(BaseModel):
    id: str
    number: str | None
    status: str | None
    amount_due: int
    amount_paid: int
    currency: str
    created: datetime
    hosted_invoice_url: str | None = None
    invoice_pdf: str | None = None


class BillingPortalIn(BaseModel):
    return_url: str = Field(min_length=8, max_length=2048)


class BillingCheckoutIn(BaseModel):
    success_url: str | None = Field(default=None, max_length=2048)
    cancel_url: str | None = Field(default=None, max_length=2048)
    plan_slug: Literal["pro", "team"] = Field(
        default="pro",
        description="Which catalog plan to subscribe to (selects Stripe price id from settings).",
    )


class BillingUrlOut(BaseModel):
    url: str


class BillingLedgerOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    external_id: str
    event_type: str
    amount_cents: int
    currency: str
    created_at: datetime
