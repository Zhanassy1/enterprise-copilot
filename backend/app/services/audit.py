from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.security import AuditLog


def write_audit_log(
    db: Session,
    *,
    event_type: str,
    workspace_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        event_type=event_type,
        workspace_id=workspace_id,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(row)
    return row
