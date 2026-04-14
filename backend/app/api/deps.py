"""
Workspace RBAC (team = workspace, scope via ``X-Workspace-Id``).

Roles (highest to lowest): owner > admin > member > viewer.
Use ``require_roles`` for non-linear permissions; ``require_at_least`` for hierarchy-based checks.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.platform_admin import user_is_platform_admin
from app.core.security import decode_token
from app.core.workspace_slug import resolve_workspace_ref_to_id
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.audit import write_audit_log
from app.services.billing_state import assert_workspace_billing_allows_writes

bearer = HTTPBearer(auto_error=False)

# Workspace role ordering for hierarchy checks (must match ``ensure_default_roles`` names).
ROLE_ORDER: dict[str, int] = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}


def role_rank(role_name: str | None) -> int | None:
    key = (role_name or "").strip().lower()
    return ROLE_ORDER.get(key)


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
    if not (x_workspace_id and str(x_workspace_id).strip()):
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")

    try:
        workspace_uuid = uuid.UUID(x_workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Workspace-Id") from None

    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_uuid, WorkspaceMember.user_id == user.id)
        .options(selectinload(WorkspaceMember.role))
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


def require_at_least(min_role: str) -> Callable[[CurrentWorkspace], WorkspaceContext]:
    """Allow this role and every role above it in ``ROLE_ORDER`` (e.g. min ``admin`` → admin + owner)."""
    m = min_role.strip().lower()
    min_rank = ROLE_ORDER.get(m)
    if min_rank is None:
        raise ValueError(f"unknown min workspace role: {min_role!r}")

    def _dep(ctx: CurrentWorkspace) -> WorkspaceContext:
        r = role_rank(ctx.membership.role.name if ctx.membership.role else None)
        if r is None or r < min_rank:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


WorkspaceReadAccess = Annotated[WorkspaceContext, Depends(require_roles("owner", "admin", "member", "viewer"))]
WorkspaceWriteAccess = Annotated[WorkspaceContext, Depends(require_roles("owner", "admin", "member"))]
# Aliases for route readability (same dependencies as the names suggest).
WorkspaceContentWriteAccess = WorkspaceWriteAccess
WorkspaceMemberManageAccess = Annotated[WorkspaceContext, Depends(require_at_least("admin"))]
WorkspaceOwnerOnly = Annotated[WorkspaceContext, Depends(require_at_least("owner"))]


def require_platform_admin(user: CurrentUser) -> User:
    if user_is_platform_admin(user):
        return user
    raise HTTPException(status_code=403, detail="Platform admin only")


PlatformAdmin = Annotated[User, Depends(require_platform_admin)]


def get_billing_write_workspace(ws: WorkspaceWriteAccess, db: DbDep) -> WorkspaceContext:
    assert_workspace_billing_allows_writes(db, ws.workspace.id)
    return ws


BillingWorkspaceWriteAccess = Annotated[WorkspaceContext, Depends(get_billing_write_workspace)]

# Billing: Stripe portal/checkout/usage/ledger/invoices — owner + admin only.
# GET /billing/subscription uses WorkspaceReadAccess (all roles) for dunning banners.
BillingOwnerAdmin = Annotated[WorkspaceContext, Depends(require_at_least("admin"))]
BillingReadAccess = BillingOwnerAdmin


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


def get_workspace_context_for_ref(workspace_ref: str, db: DbDep, user: CurrentUser) -> WorkspaceContext:
    workspace_id = resolve_workspace_ref_to_id(db, workspace_ref)
    return get_workspace_context_for_id(workspace_id, db, user)


def require_workspace_roles_for_ref(*allowed_roles: str) -> Callable[..., WorkspaceContext]:
    allowed = {r.strip().lower() for r in allowed_roles if r.strip()}

    def _dep(
        workspace_ref: str,
        db: DbDep,
        user: CurrentUser,
    ) -> WorkspaceContext:
        ctx = get_workspace_context_for_ref(workspace_ref, db, user)
        role_name = (ctx.membership.role.name or "").lower()
        if role_name not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


def require_workspace_at_least_for_id(min_role: str) -> Callable[..., WorkspaceContext]:
    m = min_role.strip().lower()
    min_rank = ROLE_ORDER.get(m)
    if min_rank is None:
        raise ValueError(f"unknown min workspace role: {min_role!r}")

    def _dep(
        workspace_id: uuid.UUID,
        db: DbDep,
        user: CurrentUser,
    ) -> WorkspaceContext:
        ctx = get_workspace_context_for_id(workspace_id, db, user)
        r = role_rank(ctx.membership.role.name if ctx.membership.role else None)
        if r is None or r < min_rank:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


def require_workspace_at_least_for_ref(min_role: str) -> Callable[..., WorkspaceContext]:
    m = min_role.strip().lower()
    min_rank = ROLE_ORDER.get(m)
    if min_rank is None:
        raise ValueError(f"unknown min workspace role: {min_role!r}")

    def _dep(
        workspace_ref: str,
        db: DbDep,
        user: CurrentUser,
    ) -> WorkspaceContext:
        ctx = get_workspace_context_for_ref(workspace_ref, db, user)
        r = role_rank(ctx.membership.role.name if ctx.membership.role else None)
        if r is None or r < min_rank:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        return ctx

    return _dep


WorkspaceInviteAdmin = Annotated[
    WorkspaceContext,
    Depends(require_workspace_at_least_for_ref("admin")),
]

# Path-scoped workspace (``/workspaces/{workspace_ref}/…``): UUID or slug; any member can read the roster.
WorkspaceReadAccessForRef = Annotated[
    WorkspaceContext,
    Depends(require_workspace_roles_for_ref("owner", "admin", "member", "viewer")),
]
