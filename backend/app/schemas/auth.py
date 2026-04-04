import uuid

from pydantic import BaseModel, EmailStr, field_validator


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    invite_token: str | None = None

    @field_validator("invite_token")
    @classmethod
    def invite_token_ok(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if len(v) < 16:
            raise ValueError("invalid_invite_token")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    invite_token: str | None = None

    @field_validator("invite_token")
    @classmethod
    def login_invite_token_ok(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if len(v) < 16:
            raise ValueError("invalid_invite_token")
        return v


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    email_verified: bool = False
    is_platform_admin: bool = False


class MeOut(UserOut):
    impersonator_id: uuid.UUID | None = None


class RefreshTokenIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class RequestPasswordResetIn(BaseModel):
    email: EmailStr


class PasswordResetIn(BaseModel):
    token: str
    new_password: str


class VerifyEmailIn(BaseModel):
    token: str

