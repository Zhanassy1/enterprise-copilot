import uuid
from datetime import datetime

from pydantic import BaseModel


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


class BillingLedgerOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    external_id: str
    event_type: str
    amount_cents: int
    currency: str
    created_at: datetime
