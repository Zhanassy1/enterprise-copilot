"""Workspace invitation create / validate / accept (token stored hashed)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.email_normalization import normalize_email
from app.core.security import generate_opaque_token, hash_opaque_token, hash_password
from app.models.user import User
from app.models.workspace import WorkspaceInvitation, WorkspaceMember
from app.services.audit import write_audit_log
from app.services.workspace_service import create_personal_workspace, ensure_default_roles

INVITEABLE_ROLES = frozenset({"admin", "member", "viewer"})
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _invite_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=int(settings.workspace_invitation_exp_hours))


def _finalize_accepted_invitation(inv: WorkspaceInvitation) -> None:
    inv.status = "accepted"
    inv.accepted_at = datetime.now(UTC)
    inv.token = None


@dataclass
class InviteValidation:
    workspace_id: uuid.UUID
    workspace_name: str
    email: str
    role: str
    expires_at: datetime | None
    user_exists: bool
    status: str


def validate_invite_token(db: Session, *, token_plain: str) -> InviteValidation:
    if not token_plain or len(token_plain) < 16:
        raise ValueError("invalid_token")
    th = hash_opaque_token(token_plain.strip())
    inv = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token == th)
        .options(selectinload(WorkspaceInvitation.role), selectinload(WorkspaceInvitation.workspace))
    )
    if not inv or not inv.workspace or not inv.role:
        raise ValueError("invalid_token")
    if inv.status != "pending":
        raise ValueError(inv.status or "invalid")
    if inv.expires_at and inv.expires_at < datetime.now(UTC):
        raise ValueError("expired")
    email = normalize_email(inv.email)
    existing = db.scalar(select(User).where(User.email == email))
    return InviteValidation(
        workspace_id=inv.workspace_id,
        workspace_name=inv.workspace.name,
        email=email,
        role=(inv.role.name or "").lower(),
        expires_at=inv.expires_at,
        user_exists=existing is not None,
        status=inv.status,
    )


def create_invitation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    email_raw: str,
    role_name: str,
    invited_by_user_id: uuid.UUID,
) -> tuple[WorkspaceInvitation, str]:
    """Create or refresh a pending invitation. Returns (invitation row, plain_token for email)."""
    email = normalize_email(email_raw)
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("invalid_email")
    role_key = (role_name or "").strip().lower()
    if role_key not in INVITEABLE_ROLES:
        raise ValueError("invalid_role")
    roles = ensure_default_roles(db)
    role = roles.get(role_key)
    if not role:
        raise ValueError("invalid_role")

    user = db.scalar(select(User).where(User.email == email))
    if user:
        mem = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if mem:
            raise ValueError("already_member")

    pending = db.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.status == "pending",
        )
    )
    plain = generate_opaque_token()
    token_h = hash_opaque_token(plain)
    exp = _invite_expiry()
    if pending:
        pending.token = token_h
        pending.role_id = role.id
        pending.expires_at = exp
        pending.invited_by_user_id = invited_by_user_id
        db.flush()
        return pending, plain

    inv = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        invited_by_user_id=invited_by_user_id,
        email=email,
        role_id=role.id,
        token=token_h,
        status="pending",
        expires_at=exp,
    )
    db.add(inv)
    db.flush()
    return inv, plain


def revoke_invitation(db: Session, *, workspace_id: uuid.UUID, invitation_id: uuid.UUID) -> WorkspaceInvitation | None:
    inv = db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
        )
    )
    if not inv or inv.status != "pending":
        return None
    inv.status = "revoked"
    inv.token = None
    db.flush()
    return inv


def _accept_invite_existing_user(
    db: Session,
    *,
    token_plain: str,
    user: User,
) -> uuid.UUID:
    th = hash_opaque_token(token_plain.strip())
    inv = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token == th)
        .options(selectinload(WorkspaceInvitation.role))
    )
    if not inv or not inv.role:
        raise ValueError("invalid_token")
    if inv.status != "pending":
        raise ValueError(inv.status or "invalid")
    if inv.expires_at and inv.expires_at < datetime.now(UTC):
        raise ValueError("expired")
    if normalize_email(user.email) != normalize_email(inv.email):
        raise ValueError("email_mismatch")

    dup = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == inv.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if dup:
        _finalize_accepted_invitation(inv)
        db.flush()
        return inv.workspace_id

    db.add(
        WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=inv.workspace_id,
            user_id=user.id,
            role_id=inv.role_id,
        )
    )
    _finalize_accepted_invitation(inv)
    db.flush()
    write_audit_log(
        db,
        event_type="invite.accepted",
        workspace_id=inv.workspace_id,
        user_id=user.id,
        target_type="workspace_invitation",
        target_id=str(inv.id),
        metadata={"email": inv.email},
    )
    return inv.workspace_id


def _accept_invite_new_user(
    db: Session,
    *,
    token_plain: str,
    password: str,
    full_name: str | None,
) -> tuple[User, uuid.UUID]:
    th = hash_opaque_token(token_plain.strip())
    inv = db.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token == th)
        .options(selectinload(WorkspaceInvitation.role))
    )
    if not inv or not inv.role:
        raise ValueError("invalid_token")
    if inv.status != "pending":
        raise ValueError(inv.status or "invalid")
    if inv.expires_at and inv.expires_at < datetime.now(UTC):
        raise ValueError("expired")
    email = normalize_email(inv.email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise ValueError("user_exists")

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=(full_name or "").strip() or None,
        email_verified=False,
    )
    db.add(user)
    db.flush()
    create_personal_workspace(db, user)
    db.add(
        WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=inv.workspace_id,
            user_id=user.id,
            role_id=inv.role_id,
        )
    )
    _finalize_accepted_invitation(inv)
    db.flush()
    write_audit_log(
        db,
        event_type="invite.accepted",
        workspace_id=inv.workspace_id,
        user_id=user.id,
        target_type="workspace_invitation",
        target_id=str(inv.id),
        metadata={"email": email, "new_user": True},
    )
    return user, inv.workspace_id


def resend_invitation(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    invitation_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
) -> tuple[WorkspaceInvitation, str]:
    inv = db.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
        )
        .options(selectinload(WorkspaceInvitation.role))
    )
    if not inv or inv.status != "pending":
        raise ValueError("not_found")
    plain = generate_opaque_token()
    inv.token = hash_opaque_token(plain)
    inv.expires_at = _invite_expiry()
    inv.invited_by_user_id = invited_by_user_id
    db.flush()
    return inv, plain


def list_invitations(db: Session, workspace_id: uuid.UUID) -> list[WorkspaceInvitation]:
    """Pending invitations for a workspace (ordered newest first)."""
    rows = db.scalars(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.workspace_id == workspace_id)
        .where(WorkspaceInvitation.status == "pending")
        .options(selectinload(WorkspaceInvitation.role))
        .order_by(WorkspaceInvitation.created_at.desc())
    ).all()
    return list(rows)


def accept_invitation(
    db: Session,
    *,
    token_plain: str,
    existing_user: User | None = None,
    password: str | None = None,
    full_name: str | None = None,
) -> tuple[User, uuid.UUID]:
    """
    Accept an invitation: either as a logged-in user (existing_user) or new account (password required).
    Does not commit the session.
    """
    if existing_user is not None:
        ws_id = _accept_invite_existing_user(db, token_plain=token_plain, user=existing_user)
        return existing_user, ws_id
    if password is None or len(password) < 8:
        raise ValueError("password_required")
    return _accept_invite_new_user(db, token_plain=token_plain, password=password, full_name=full_name)
