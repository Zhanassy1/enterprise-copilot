from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
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
    actor_user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    resolved_actor = actor_user_id if actor_user_id is not None else user_id
    row = AuditLog(
        event_type=event_type,
        workspace_id=workspace_id,
        user_id=user_id,
        actor_user_id=resolved_actor,
        ip_address=ip_address,
        user_agent=user_agent,
        target_type=target_type,
        target_id=target_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(row)
    return row


def write_audit_from_request(
    db: Session,
    request: Request,
    *,
    event_type: str,
    workspace_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> AuditLog:
    ua = (request.headers.get("user-agent") or "").strip()
    if len(ua) > 512:
        ua = ua[:512]
    return write_audit_log(
        db,
        event_type=event_type,
        workspace_id=workspace_id,
        user_id=user_id,
        actor_user_id=actor_user_id,
        ip_address=get_client_ip(request),
        user_agent=ua or None,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )
