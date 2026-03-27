from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbDep
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.models.security import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginIn,
    PasswordResetIn,
    RefreshTokenIn,
    RegisterIn,
    RequestPasswordResetIn,
    Token,
    UserOut,
    VerifyEmailIn,
)
from app.services.audit import write_audit_log
from app.services.email_service import send_password_reset_email, send_verification_email
from app.services.workspace_service import create_personal_workspace

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, db: DbDep) -> UserOut:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user)
    db.flush()
    create_personal_workspace(db, user)
    verify_token = generate_opaque_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_opaque_token(verify_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=int(settings.email_verification_token_exp_minutes)),
            used=False,
        )
    )
    send_verification_email(user.email, verify_token)
    write_audit_log(
        db,
        event_type="auth.register",
        workspace_id=None,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email},
    )
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, email_verified=bool(user.email_verified))


@router.post("/login", response_model=Token)
def login(payload: LoginIn, db: DbDep) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    refresh_token = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_opaque_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=int(settings.refresh_token_exp_days)),
            revoked=False,
        )
    )
    write_audit_log(
        db,
        event_type="auth.login",
        workspace_id=None,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email},
    )
    db.commit()
    return Token(access_token=create_access_token(str(user.id)), refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
def refresh_token(payload: RefreshTokenIn, db: DbDep) -> Token:
    token_hash = hash_opaque_token(payload.refresh_token)
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False)))
    if not token_row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    token_row.revoked = True
    new_refresh = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=token_row.user_id,
            token_hash=hash_opaque_token(new_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=int(settings.refresh_token_exp_days)),
            revoked=False,
        )
    )
    db.commit()
    return Token(access_token=create_access_token(str(token_row.user_id)), refresh_token=new_refresh)


@router.post("/request-password-reset")
def request_password_reset(payload: RequestPasswordResetIn, db: DbDep) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        return {"ok": True}
    token = generate_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=int(settings.password_reset_token_exp_minutes)),
            used=False,
        )
    )
    send_password_reset_email(user.email, token)
    write_audit_log(
        db,
        event_type="auth.password_reset_requested",
        workspace_id=None,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email},
    )
    db.commit()
    return {"ok": True}


@router.post("/reset-password")
def reset_password(payload: PasswordResetIn, db: DbDep) -> dict:
    token_hash = hash_opaque_token(payload.token)
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash, PasswordResetToken.used.is_(False))
    )
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.scalar(select(User).where(User.id == row.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    row.used = True
    write_audit_log(
        db,
        event_type="auth.password_reset_completed",
        workspace_id=None,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
    )
    db.add(user)
    db.add(row)
    db.commit()
    return {"ok": True}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailIn, db: DbDep) -> dict:
    token_hash = hash_opaque_token(payload.token)
    row = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash, EmailVerificationToken.used.is_(False))
    )
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = db.scalar(select(User).where(User.id == row.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    row.used = True
    write_audit_log(
        db,
        event_type="auth.email_verified",
        workspace_id=None,
        user_id=user.id,
        target_type="user",
        target_id=str(user.id),
    )
    db.add(user)
    db.add(row)
    db.commit()
    return {"ok": True}
