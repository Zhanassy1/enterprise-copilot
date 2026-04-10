import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["argon2", "pbkdf2_sha256"],
    deprecated=["pbkdf2_sha256"],
)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password_with_rehash(password: str, password_hash: str) -> tuple[bool, str | None]:
    verified, new_hash = pwd_context.verify_and_update(password, password_hash)
    return bool(verified), new_hash


def verify_password(password: str, password_hash: str) -> bool:
    ok, _ = verify_password_with_rehash(password, password_hash)
    return ok


def create_access_token(subject: str, *, expires_minutes: int | None = None, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(tz=UTC)
    exp = now + timedelta(minutes=expires_minutes or settings.access_token_exp_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={
            "require": ["exp", "sub", "iat", "jti", "aud", "iss"],
        },
    )


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
