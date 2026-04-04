"""Unit tests for workspace slug helpers (no DB)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.workspace_slug import RESERVED_SLUGS, slugify_name, validate_slug_segment


def test_slugify_basic() -> None:
    assert slugify_name("My Cool Company") == "my-cool-company"


def test_slugify_reserved_gets_suffix() -> None:
    s = slugify_name("Admin")
    assert s.endswith("-ws") or s not in RESERVED_SLUGS


def test_validate_slug_accepts() -> None:
    assert validate_slug_segment("acme-corp") == "acme-corp"


def test_validate_slug_rejects_empty() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_slug_segment("")
    assert exc.value.status_code == 400


def test_validate_slug_rejects_invalid_chars() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_slug_segment("bad_slug")
    assert exc.value.status_code == 400
