import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.audit import write_audit_log

bearer = HTTPBearer(auto_error=False)


DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class WorkspaceContext:
    workspace: Workspace
    membership: WorkspaceMember


def get_workspace_context(
    db: DbDep,
    user: CurrentUser,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
) -> WorkspaceContext:
    env = settings.environment.lower().strip()
    if env == "production" and settings.require_workspace_header_in_production:
        if not (x_workspace_id and str(x_workspace_id).strip()):
            raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")

    if x_workspace_id:
        try:
            workspace_uuid = uuid.UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Workspace-Id") from None

        membership = db.scalar(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_uuid, WorkspaceMember.user_id == user.id)
            .limit(1)
        )
        if not membership:
            write_audit_log(
                db,
                event_type="workspace.access_denied",
                workspace_id=workspace_uuid,
                user_id=user.id,
                target_type="workspace",
                target_id=str(workspace_uuid),
                metadata={"reason": "not_a_member"},
            )
            db.commit()
            raise HTTPException(status_code=403, detail="No access to workspace")
    else:
        membership = db.scalar(
            select(WorkspaceMember)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(Workspace.personal_for_user_id.desc().nullslast(), Workspace.created_at.asc())
            .limit(1)
        )
        if not membership:
            raise HTTPException(status_code=403, detail="No workspace membership found")

    workspace = db.scalar(select(Workspace).where(Workspace.id == membership.workspace_id))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceContext(workspace=workspace, membership=membership)


CurrentWorkspace = Annotated[WorkspaceContext, Depends(get_workspace_context)]


def require_roles(*allowed_roles: str) -> Callable[[CurrentWorkspace], WorkspaceContext]:
    allowed = {r.strip().lower() for r in allowed_roles if r.strip()}

    def _dep(ctx: CurrentWorkspace) -> WorkspaceContext:
        role_name = (ctx.membership.role.name or "").lower()
        if role_name not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


WorkspaceReadAccess = Annotated[WorkspaceContext, Depends(require_roles("owner", "admin", "member", "viewer"))]
WorkspaceWriteAccess = Annotated[WorkspaceContext, Depends(require_roles("owner", "admin", "member"))]
