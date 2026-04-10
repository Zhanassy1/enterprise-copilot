"""Canonical email for lookups and storage: strip whitespace, ASCII-lowercase local part domain."""

from __future__ import annotations


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()
