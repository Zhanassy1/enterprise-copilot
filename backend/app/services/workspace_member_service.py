"""Workspace membership list and mutations (RBAC-enforced in router + here)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import WorkspaceContext
from app.models.workspace import Workspace, WorkspaceMember
from app.services.workspace_service import ensure_default_roles


def list_workspace_members(db: Session, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
    return list(
        db.scalars(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMember.user), selectinload(WorkspaceMember.role))
            .order_by(WorkspaceMember.created_at.asc())
        ).all()
    )


def get_membership_for_user(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .options(selectinload(WorkspaceMember.role), selectinload(WorkspaceMember.user))
    )


def assert_can_update_target_role(
    *,
    actor: WorkspaceContext,
    workspace: Workspace,
    target: WorkspaceMember,
) -> None:
    """Raise HTTPException if actor must not change this member's role."""
    target_uid = target.user_id
    target_role = (target.role.name or "").lower() if target.role else ""

    if target_uid == workspace.owner_user_id:
        raise HTTPException(status_code=403, detail="Cannot modify workspace owner")

    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Cannot modify owner membership")

    actor_role = (actor.membership.role.name or "").lower()

    if actor_role == "admin":
        if target_role in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Insufficient workspace role")


def assert_can_remove_target_member(
    *,
    actor: WorkspaceContext,
    workspace: Workspace,
    target: WorkspaceMember,
) -> None:
    """Raise HTTPException if actor must not remove this member (admin may remove self to leave)."""
    target_uid = target.user_id
    target_role = (target.role.name or "").lower() if target.role else ""

    if target_uid == workspace.owner_user_id:
        raise HTTPException(status_code=403, detail="Cannot remove workspace owner")

    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove owner membership")

    actor_role = (actor.membership.role.name or "").lower()

    if actor_role == "admin":
        if target_role in ("owner", "admin"):
            if target.user_id == actor.membership.user_id and target_role == "admin":
                return
            raise HTTPException(status_code=403, detail="Insufficient workspace role")


def update_member_role(
    db: Session,
    *,
    actor: WorkspaceContext,
    workspace: Workspace,
    target_user_id: uuid.UUID,
    new_role_name: str,
) -> WorkspaceMember:
    key = new_role_name.strip().lower()
    if key == "owner":
        raise HTTPException(status_code=400, detail="Cannot assign owner role via API")

    roles = ensure_default_roles(db)
    if key not in roles:
        raise HTTPException(status_code=400, detail="Invalid role")

    target = get_membership_for_user(db, workspace.id, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    assert_can_update_target_role(actor=actor, workspace=workspace, target=target)

    if target.user_id == actor.membership.user_id:
        raise HTTPException(status_code=403, detail="Cannot change own role here")

    target.role_id = roles[key].id
    db.flush()
    db.refresh(target)
    return target


def remove_member(
    db: Session,
    *,
    actor: WorkspaceContext,
    workspace: Workspace,
    target_user_id: uuid.UUID,
) -> tuple[uuid.UUID, str]:
    target = get_membership_for_user(db, workspace.id, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    assert_can_remove_target_member(actor=actor, workspace=workspace, target=target)

    email = (target.user.email if target.user else "") or ""
    uid = target.user_id
    db.delete(target)
    db.flush()
    return uid, email
