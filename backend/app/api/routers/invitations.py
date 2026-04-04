import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbDep, OptionalUser, WorkspaceInviteAdmin
from app.core.config import settings
from app.core.security import create_access_token, generate_opaque_token, hash_opaque_token
from app.models.security import RefreshToken
from app.schemas.auth import Token
from app.schemas.invitations_api import (
    InvitationCreateIn,
    InvitationOut,
    InviteAcceptIn,
    InviteValidateOut,
)
from app.services.audit import write_audit_log
from app.services.email_service import send_workspace_invite_email
from app.services.invitation_service import (
    accept_invite_existing_user,
    accept_invite_new_user,
    create_or_refresh_invitation,
    list_pending_invitations,
    resend_invitation,
    revoke_invitation,
    validate_invite_token,
)

router = APIRouter(tags=["invitations"])


@router.get("/invitations/validate", response_model=InviteValidateOut)
def validate_invitation(
    db: DbDep,
    token: Annotated[str, Query(min_length=16)],
) -> InviteValidateOut:
    try:
        v = validate_invite_token(db, token_plain=token)
    except ValueError as e:
        code = str(e.args[0] if e.args else "invalid")
        raise HTTPException(status_code=400, detail=code) from e
    return InviteValidateOut(
        workspace_id=v.workspace_id,
        workspace_name=v.workspace_name,
        email=v.email,
        role=v.role,
        expires_at=v.expires_at,
        user_exists=v.user_exists,
    )


def _issue_login_token(db: DbDep, user_id: uuid.UUID) -> Token:
    refresh_token = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_opaque_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=int(settings.refresh_token_exp_days)),
            revoked=False,
        )
    )
    return Token(access_token=create_access_token(str(user_id)), refresh_token=refresh_token)


@router.post("/invitations/accept", response_model=Token)
def accept_invitation(
    payload: InviteAcceptIn,
    db: DbDep,
    optional_user: OptionalUser,
) -> Token:
    try:
        preview = validate_invite_token(db, token_plain=payload.token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e.args[0] if e.args else "invalid")) from e

    if preview.user_exists:
        if not optional_user:
            raise HTTPException(status_code=401, detail="Login required to accept this invitation")
        try:
            accept_invite_existing_user(db, token_plain=payload.token, user=optional_user)
        except ValueError as e:
            code = str(e.args[0] if e.args else "invalid")
            if code == "email_mismatch":
                raise HTTPException(status_code=403, detail=code) from e
            raise HTTPException(status_code=400, detail=code) from e
        tok = _issue_login_token(db, optional_user.id)
        db.commit()
        return tok

    if not payload.password or len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="password required (min 8 characters)")
    if optional_user:
        raise HTTPException(status_code=400, detail="Use logged-out acceptance for new accounts")
    try:
        user, _ws = accept_invite_new_user(
            db,
            token_plain=payload.token,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e.args[0] if e.args else "invalid")) from e
    tok = _issue_login_token(db, user.id)
    db.commit()
    return tok


@router.post("/workspaces/{workspace_ref}/invitations", response_model=InvitationOut)
def create_workspace_invitation(
    body: InvitationCreateIn,
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> InvitationOut:
    workspace_id = ws.workspace.id
    try:
        inv, plain = create_or_refresh_invitation(
            db,
            workspace_id=workspace_id,
            email_raw=body.email,
            role_name=body.role,
            invited_by_user_id=ws.membership.user_id,
        )
    except ValueError as e:
        code = str(e.args[0] if e.args else "invalid")
        if code == "already_member":
            raise HTTPException(status_code=409, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e
    wname = ws.workspace.name
    role_name = body.role.strip().lower()
    db.flush()
    send_workspace_invite_email(
        to_email=inv.email,
        token=plain,
        workspace_name=wname,
        role_name=role_name,
    )
    write_audit_log(
        db,
        event_type="invite.created",
        workspace_id=workspace_id,
        user_id=ws.membership.user_id,
        target_type="workspace_invitation",
        target_id=str(inv.id),
        metadata={"email": inv.email, "role": body.role},
    )
    db.commit()
    db.refresh(inv)
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=role_name,
        status=inv.status,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
    )


@router.get("/workspaces/{workspace_ref}/invitations", response_model=list[InvitationOut])
def list_workspace_invitations(
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> list[InvitationOut]:
    workspace_id = ws.workspace.id
    rows = list_pending_invitations(db, workspace_id)
    out: list[InvitationOut] = []
    for inv in rows:
        rname = (inv.role.name or "").lower() if inv.role else ""
        out.append(
            InvitationOut(
                id=inv.id,
                email=inv.email,
                role=rname,
                status=inv.status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
        )
    return out


@router.post("/workspaces/{workspace_ref}/invitations/{invitation_id}/revoke")
def revoke_workspace_invitation(
    invitation_id: uuid.UUID,
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> dict[str, str]:
    workspace_id = ws.workspace.id
    inv = revoke_invitation(db, workspace_id=workspace_id, invitation_id=invitation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    write_audit_log(
        db,
        event_type="invite.revoked",
        workspace_id=workspace_id,
        user_id=ws.membership.user_id,
        target_type="workspace_invitation",
        target_id=str(invitation_id),
        metadata={"email": inv.email},
    )
    db.commit()
    return {"status": "revoked"}


@router.post("/workspaces/{workspace_ref}/invitations/{invitation_id}/resend", response_model=InvitationOut)
def resend_workspace_invitation(
    invitation_id: uuid.UUID,
    db: DbDep,
    ws: WorkspaceInviteAdmin,
) -> InvitationOut:
    workspace_id = ws.workspace.id
    try:
        inv, plain = resend_invitation(
            db,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            invited_by_user_id=ws.membership.user_id,
        )
    except ValueError as e:
        if str(e.args[0] if e.args else "") == "not_found":
            raise HTTPException(status_code=404, detail="Invitation not found") from e
        raise HTTPException(status_code=400, detail="invalid") from e
    wname = ws.workspace.name
    role_name = (inv.role.name or "").lower() if inv.role else "member"
    send_workspace_invite_email(
        to_email=inv.email,
        token=plain,
        workspace_name=wname,
        role_name=role_name or "member",
    )
    write_audit_log(
        db,
        event_type="invite.resent",
        workspace_id=workspace_id,
        user_id=ws.membership.user_id,
        target_type="workspace_invitation",
        target_id=str(inv.id),
        metadata={"email": inv.email},
    )
    db.commit()
    db.refresh(inv)
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=role_name or "member",
        status=inv.status,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
    )
