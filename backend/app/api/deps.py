import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.platform_admin import user_is_platform_admin
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.audit import write_audit_log
from app.services.billing_state import assert_workspace_billing_allows_writes

bearer = HTTPBearer(auto_error=False)


DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
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

    request.state.impersonator_id = None
    imp = payload.get("imp")
    if imp:
        try:
            request.state.impersonator_id = uuid.UUID(str(imp))
        except ValueError:
            request.state.impersonator_id = None

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_current_user(
    request: Request,
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | None:
    if not creds or not creds.credentials:
        return None
    try:
        payload = decode_token(creds.credentials)
        sub = payload.get("sub")
        if not sub:
            return None
        user_id = uuid.UUID(str(sub))
    except (ExpiredSignatureError, PyJWTError, ValueError):
        return None
    request.state.impersonator_id = None
    imp = payload.get("imp")
    if imp:
        try:
            request.state.impersonator_id = uuid.UUID(str(imp))
        except ValueError:
            request.state.impersonator_id = None
    user = db.scalar(select(User).where(User.id == user_id))
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_current_user)]


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


def require_platform_admin(user: CurrentUser) -> User:
    if user_is_platform_admin(user):
        return user
    raise HTTPException(status_code=403, detail="Platform admin only")


PlatformAdmin = Annotated[User, Depends(require_platform_admin)]


def get_billing_write_workspace(ws: WorkspaceWriteAccess, db: DbDep) -> WorkspaceContext:
    assert_workspace_billing_allows_writes(db, ws.workspace.id)
    return ws


BillingWorkspaceWriteAccess = Annotated[WorkspaceContext, Depends(get_billing_write_workspace)]

BillingOwnerAdmin = Annotated[WorkspaceContext, Depends(require_roles("owner", "admin"))]


def get_workspace_context_for_id(
    workspace_id: uuid.UUID,
    db: DbDep,
    user: CurrentUser,
) -> WorkspaceContext:
    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .options(selectinload(WorkspaceMember.role))
    )
    if not membership:
        write_audit_log(
            db,
            event_type="workspace.access_denied",
            workspace_id=workspace_id,
            user_id=user.id,
            target_type="workspace",
            target_id=str(workspace_id),
            metadata={"reason": "not_a_member"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="No access to workspace")
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceContext(workspace=workspace, membership=membership)


def require_workspace_roles_for_id(*allowed_roles: str) -> Callable[..., WorkspaceContext]:
    allowed = {r.strip().lower() for r in allowed_roles if r.strip()}

    def _dep(
        workspace_id: uuid.UUID,
        db: DbDep,
        user: CurrentUser,
    ) -> WorkspaceContext:
        ctx = get_workspace_context_for_id(workspace_id, db, user)
        role_name = (ctx.membership.role.name or "").lower()
        if role_name not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


WorkspaceInviteAdmin = Annotated[
    WorkspaceContext,
    Depends(require_workspace_roles_for_id("owner", "admin")),
]
