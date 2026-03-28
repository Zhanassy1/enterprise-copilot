from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep
from app.models.workspace import WorkspaceMember
from app.schemas.workspace import WorkspaceOut

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(db: DbDep, user: CurrentUser) -> list[WorkspaceOut]:
    members = db.scalars(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .options(selectinload(WorkspaceMember.workspace), selectinload(WorkspaceMember.role))
    ).all()
    out: list[WorkspaceOut] = []
    for m in members:
        if not m.workspace or not m.role:
            continue
        out.append(
            WorkspaceOut(
                id=m.workspace.id,
                name=m.workspace.name,
                role=(m.role.name or "").lower(),
            )
        )
    return out
