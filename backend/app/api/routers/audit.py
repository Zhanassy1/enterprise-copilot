from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbDep, WorkspaceReadAccess
from app.models.security import AuditLog
from app.schemas.audit_api import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogOut])
def list_audit_logs(
    db: DbDep,
    ws: WorkspaceReadAccess,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditLogOut]:
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == ws.workspace.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        AuditLogOut(
            id=r.id,
            event_type=r.event_type,
            user_id=r.user_id,
            actor_user_id=r.actor_user_id,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            target_type=r.target_type,
            target_id=r.target_id,
            metadata_json=r.metadata_json,
            created_at=r.created_at,
        )
        for r in rows
    ]
