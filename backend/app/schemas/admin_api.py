import uuid

from pydantic import BaseModel, Field


class ImpersonateIn(BaseModel):
    user_id: uuid.UUID


class QuotaAdjustIn(BaseModel):
    monthly_request_limit: int | None = Field(default=None, ge=0)
    monthly_token_limit: int | None = Field(default=None, ge=0)
    extend_grace_days: int | None = Field(default=None, ge=1, le=365)
    plan_slug: str | None = Field(default=None, max_length=32)
