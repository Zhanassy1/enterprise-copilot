"""Unit tests for email normalization, JWT claims, and password hash upgrade (no DB)."""

from __future__ import annotations

import uuid

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.email_normalization import normalize_email
from app.core.security import (
    ALGORITHM,
    create_access_token,
    decode_token,
    hash_password,
    verify_password_with_rehash,
)
from app.schemas.auth import LoginIn, RegisterIn


def test_normalize_email_strips_lowercase() -> None:
    assert normalize_email("  User@Example.COM  ") == "user@example.com"
    assert normalize_email("") == ""


def test_register_in_email_canonical() -> None:
    m = RegisterIn.model_validate(
        {
            "email": "Alias@Example.COM",
            "password": "LongEnough1!",
            "full_name": None,
        }
    )
    assert m.email == "alias@example.com"


def test_login_in_email_canonical() -> None:
    m = LoginIn.model_validate({"email": "Ghost@Example.COM", "password": "x"})
    assert m.email == "ghost@example.com"


def test_access_token_roundtrip_claims() -> None:
    uid = str(uuid.uuid4())
    tok = create_access_token(uid)
    payload = decode_token(tok)
    assert payload["sub"] == uid
    assert payload.get("jti")
    assert payload.get("iss")
    assert payload.get("aud")
    assert "exp" in payload and "iat" in payload


def test_access_token_expires_minutes_zero_not_replaced_by_default() -> None:
    uid = str(uuid.uuid4())
    tok = create_access_token(uid, expires_minutes=0)
    # exp == iat; decode_token() would often fail with ExpiredSignatureError before this assert.
    payload = jwt.decode(
        tok,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={
            "verify_exp": False,
            "require": ["exp", "sub", "iat", "jti", "aud", "iss"],
        },
    )
    assert payload["exp"] - payload["iat"] == 0


def test_new_password_uses_argon2_scheme() -> None:
    h = hash_password("UnitTestPwd1!")
    assert "$argon2" in h


def test_legacy_pbkdf2_verify_and_upgrade() -> None:
    legacy = CryptContext(schemes=["pbkdf2_sha256"])
    old_hash = legacy.hash("LegacyPwd1!")
    ok, new_hash = verify_password_with_rehash("LegacyPwd1!", old_hash)
    assert ok is True
    assert new_hash is not None
    assert "$argon2" in new_hash
