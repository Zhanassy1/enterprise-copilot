import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None
    target_type: str | None
    target_id: str | None
    metadata_json: str | None
    created_at: datetime
