import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Role, Workspace, WorkspaceMember


def ensure_default_roles(db: Session) -> dict[str, Role]:
    names = ("owner", "admin", "member", "viewer")
    existing = db.scalars(select(Role).where(Role.name.in_(names))).all()
    by_name = {r.name: r for r in existing}
    for role_name in names:
        if role_name not in by_name:
            role = Role(id=uuid.uuid4(), name=role_name)
            db.add(role)
            db.flush()
            by_name[role_name] = role
    return by_name


def create_personal_workspace(db: Session, user: User) -> Workspace:
    roles = ensure_default_roles(db)
    workspace = Workspace(
        id=uuid.uuid4(),
        name=f"{(user.full_name or user.email).strip()} personal workspace",
        owner_user_id=user.id,
        personal_for_user_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            user_id=user.id,
            role_id=roles["owner"].id,
        )
    )
    db.flush()
    return workspace
