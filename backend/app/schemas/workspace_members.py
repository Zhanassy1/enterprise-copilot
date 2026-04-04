import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    joined_at: datetime


class WorkspaceMemberRoleUpdateIn(BaseModel):
    role: str = Field(min_length=3, max_length=32)
