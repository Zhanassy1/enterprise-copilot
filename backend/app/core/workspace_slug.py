"""Human-readable workspace slugs for URLs (indexed, not secret — authZ still applies)."""

from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$")

RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        "admin",
        "api",
        "login",
        "logout",
        "register",
        "invite",
        "w",
        "settings",
        "documents",
        "team",
        "chat",
        "billing",
        "audit",
        "jobs",
        "search",
        "pricing",
        "static",
        "public",
        "assets",
        "health",
        "metrics",
        "v1",
        "auth",
    }
)


def slugify_name(name: str) -> str:
    """Normalize a display name into a candidate slug (may need uniquifying)."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if len(s) < 3:
        s = "workspace"
    if len(s) > 64:
        s = s[:64].rstrip("-")
    if not SLUG_RE.match(s):
        s = "workspace"
    if s in RESERVED_SLUGS:
        s = f"{s}-ws"
    return s[:64]


def ensure_unique_slug(db: Session, base: str) -> str:
    """Pick a unique slug given a base string (queries existing rows)."""
    candidate = base[:64] if base else "workspace"
    n = 0
    while True:
        c = candidate if n == 0 else f"{base[:50]}-{n}"[:64]
        existing = db.scalar(select(Workspace.id).where(Workspace.slug == c).limit(1))
        if not existing:
            return c
        n += 1


def validate_slug_segment(slug: str) -> str:
    """Return normalized slug or raise HTTP 400."""
    s = (slug or "").strip().lower()
    if not s or len(s) > 64 or not SLUG_RE.match(s):
        raise HTTPException(status_code=400, detail="Invalid workspace slug")
    return s


def resolve_workspace_ref_to_id(db: Session, ref: str) -> uuid.UUID:
    """
    Path segment: UUID (existing workspace id) or slug.
    """
    ref = (ref or "").strip()
    if not ref:
        raise HTTPException(status_code=400, detail="Invalid workspace ref")

    try:
        uid = uuid.UUID(ref)
    except ValueError:
        uid = None

    if uid is not None:
        ws = db.scalar(select(Workspace).where(Workspace.id == uid))
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws.id

    slug = validate_slug_segment(ref)
    ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws.id
