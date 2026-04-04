import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import DbDep, WorkspaceInviteAdmin, WorkspaceReadAccessForRef
from app.schemas.workspace_members import WorkspaceMemberOut, WorkspaceMemberRoleUpdateIn
from app.services.audit import write_audit_log
from app.services.workspace_member_service import (
    list_workspace_members,
    remove_member,
    update_member_role,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/{workspace_ref}/members", response_model=list[WorkspaceMemberOut])
def list_members(
    db: DbDep,
    ws: WorkspaceReadAccessForRef,
) -> list[WorkspaceMemberOut]:
    rows = list_workspace_members(db, ws.workspace.id)
    out: list[WorkspaceMemberOut] = []
    for m in rows:
        if not m.user or not m.role:
            continue
        out.append(
            WorkspaceMemberOut(
                user_id=m.user_id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=(m.role.name or "").lower(),
                joined_at=m.created_at,
            )
        )
    return out


@router.patch("/{workspace_ref}/members/{user_id}", response_model=WorkspaceMemberOut)
def patch_member_role(
    user_id: uuid.UUID,
    body: WorkspaceMemberRoleUpdateIn,
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> WorkspaceMemberOut:
    m = update_member_role(db, actor=ws, workspace=ws.workspace, target_user_id=user_id, new_role_name=body.role)
    if not m.user or not m.role:
        raise HTTPException(status_code=500, detail="Member state error")
    out = WorkspaceMemberOut(
        user_id=m.user_id,
        email=m.user.email,
        full_name=m.user.full_name,
        role=(m.role.name or "").lower(),
        joined_at=m.created_at,
    )
    write_audit_log(
        db,
        event_type="member.role_changed",
        workspace_id=ws.workspace.id,
        user_id=ws.membership.user_id,
        target_type="workspace_member",
        target_id=str(user_id),
        metadata={"new_role": body.role.strip().lower()},
    )
    db.commit()
    return out


@router.delete("/{workspace_ref}/members/{user_id}")
def delete_member(
    user_id: uuid.UUID,
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> dict[str, str]:
    removed_id, email = remove_member(db, actor=ws, workspace=ws.workspace, target_user_id=user_id)
    write_audit_log(
        db,
        event_type="member.removed",
        workspace_id=ws.workspace.id,
        user_id=ws.membership.user_id,
        target_type="workspace_member",
        target_id=str(removed_id),
        metadata={"email": email},
    )
    db.commit()
    return {"status": "removed"}
