"""user_is_platform_admin: DB flag vs PLATFORM_ADMIN_EMAILS."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.platform_admin import user_is_platform_admin


def _user(*, db_admin: bool = False, email: str = "u@example.com") -> MagicMock:
    u = MagicMock()
    u.is_platform_admin = db_admin
    u.email = email
    return u


def test_true_when_db_flag() -> None:
    assert user_is_platform_admin(_user(db_admin=True)) is True


def test_false_when_not_in_list() -> None:
    assert user_is_platform_admin(_user(db_admin=False, email="nobody@example.com")) is False


def test_true_when_email_in_platform_admin_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "platform_admin_emails", "a@x.com, b@y.com", raising=False)
    assert user_is_platform_admin(_user(db_admin=False, email="b@y.com")) is True


def test_email_match_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "platform_admin_emails", "Admin@Example.com", raising=False)
    assert user_is_platform_admin(_user(db_admin=False, email="admin@example.com")) is True
