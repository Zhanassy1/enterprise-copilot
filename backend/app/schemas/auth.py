import uuid

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    email_verified: bool = False


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

