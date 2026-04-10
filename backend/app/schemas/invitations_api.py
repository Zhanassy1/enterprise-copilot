import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.email_normalization import normalize_email


class InvitationCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(min_length=3, max_length=32, description="admin | member | viewer")

    @field_validator("email")
    @classmethod
    def email_canonical_invite_create(cls, v: str) -> str:
        return normalize_email(v)


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime | None
    created_at: datetime
    # Only populated when `email_capture_mode` is enabled (tests / local dev), never in production mail flow.
    plain_token: str | None = None


class InviteValidateOut(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    email: str
    role: str
    expires_at: datetime | None
    user_exists: bool


class InviteAcceptIn(BaseModel):
    token: str = Field(min_length=16)
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = Field(default=None, max_length=255)
