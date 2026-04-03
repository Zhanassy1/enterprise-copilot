import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InvitationCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(min_length=3, max_length=32, description="admin | member | viewer")


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime | None
    created_at: datetime


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
