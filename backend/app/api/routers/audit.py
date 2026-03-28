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
    event_type: str | None = Query(default=None, description="Filter by event_type prefix match"),
) -> list[AuditLogOut]:
    q = select(AuditLog).where(AuditLog.workspace_id == ws.workspace.id)
    if event_type and event_type.strip():
        et = event_type.strip()
        q = q.where(AuditLog.event_type == et)
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        AuditLogOut(
            id=r.id,
            event_type=r.event_type,
            user_id=r.user_id,
            target_type=r.target_type,
            target_id=r.target_id,
            metadata_json=r.metadata_json,
            created_at=r.created_at,
        )
        for r in rows
    ]
