"""Compile PostgreSQL tsquery strings for hybrid keyword retrieval (with fallbacks)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ILIKE substring bonus only for short queries (avoids heavy scans on long pasted text).
KEYWORD_ILIKE_MAX_LEN = 64

_CODE_LIKE_RE = re.compile(r"^[A-Za-z0-9А-Яа-яЁё][A-Za-z0-9А-Яа-яЁё\-/.]{1,127}$")
# Mostly token/symbol-heavy (SKUs, dotted numbers) — prefer plainto_tsquery for simple/aux.
_CODE_RATIO_RE = re.compile(r"[A-Za-z0-9\-/.]")


def is_code_like_keyword_query(q: str) -> bool:
    s = (q or "").strip()
    if not s or len(s) > 128:
        return False
    if " " in s:
        return False
    if not _CODE_LIKE_RE.match(s):
        alnum = sum(1 for c in s if c.isalnum())
        sym = len(_CODE_RATIO_RE.findall(s))
        return len(s) >= 4 and sym >= len(s) * 0.6 and alnum >= len(s) * 0.4

    has_structural = any(c in s for c in "-/.0123456789")
    mixed_latin_case = (
        any("a" <= c <= "z" for c in s)
        and any("A" <= c <= "Z" for c in s)
    )
    allcaps_ascii_word = s.isascii() and s.isalpha() and s.isupper() and len(s) >= 4
    long_with_digit = len(s) >= 8 and any(c.isdigit() for c in s)
    return bool(
        has_structural or mixed_latin_case or allcaps_ascii_word or long_with_digit
    )


def _tsquery_text_or_empty(db: Session, stmt: str, params: dict) -> str:
    try:
        row = db.execute(text(stmt), params).scalar()
        if row is None:
            return ""
        return str(row).strip()
    except SQLAlchemyError:
        return ""


def _websearch_then_plain(db: Session, regconfig: str, q: str) -> str:
    t = _tsquery_text_or_empty(
        db,
        f"SELECT websearch_to_tsquery('{regconfig}', :q)::text",
        {"q": q},
    )
    if t:
        return t
    return _tsquery_text_or_empty(
        db,
        f"SELECT plainto_tsquery('{regconfig}', :q)::text",
        {"q": q},
    )


def _plain_only(db: Session, regconfig: str, q: str) -> str:
    return _tsquery_text_or_empty(
        db,
        f"SELECT plainto_tsquery('{regconfig}', :q)::text",
        {"q": q},
    )


def _phraseto_then_plain(db: Session, regconfig: str, q: str) -> str:
    """Prefer phrase match for SKUs / dotted codes so hyphens are not arbitrary AND splits."""
    t = _tsquery_text_or_empty(
        db,
        f"SELECT phraseto_tsquery('{regconfig}', :q)::text",
        {"q": q},
    )
    if t:
        return t
    return _plain_only(db, regconfig, q)


def prepare_keyword_tsquery_texts(db: Session, query_text: str) -> tuple[str, str, str]:
    """
    Return ``(q_ru, q_simple, q_aux)`` as ``tsquery::text`` for ``CAST(:x AS tsquery)``.
    Empty string means that arm is skipped in ``@@`` and rank.
    """
    q = (query_text or "").strip()
    if not q:
        return "", "", ""

    code = is_code_like_keyword_query(q)
    q_ru = "" if code else _websearch_then_plain(db, "russian", q)
    if code:
        q_simple = _phraseto_then_plain(db, "simple", q)
    else:
        q_simple = _websearch_then_plain(db, "simple", q)

    aux_src = q[:2000]
    if code:
        q_aux = _phraseto_then_plain(db, "simple", aux_src)
    else:
        q_aux = _plain_only(db, "simple", aux_src)

    return q_ru, q_simple, q_aux


def any_tsquery_non_empty(q_ru: str, q_simple: str, q_aux: str) -> bool:
    return bool((q_ru or "").strip() or (q_simple or "").strip() or (q_aux or "").strip())
