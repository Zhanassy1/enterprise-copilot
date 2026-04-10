"""Lowercase trim canonical emails (users + workspace_invitations)

Revision ID: 20260410_0016
Revises: 20260406_0015_reply_meta
Create Date: 2026-04-10

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260410_0016_canonical_email_lower"
down_revision = "20260406_0015_reply_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dup_users = conn.execute(
        sa.text(
            """
            SELECT lower(trim(email)) AS canonical
            FROM users
            GROUP BY lower(trim(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dup_users:
        samples = [r[0] for r in dup_users[:20]]
        raise RuntimeError(
            "Refusing to normalize users.email: duplicate canonical addresses. "
            f"Examples (up to 20): {samples}"
        )

    dup_inv = conn.execute(
        sa.text(
            """
            SELECT workspace_id::text, lower(trim(email)) AS canonical
            FROM workspace_invitations
            GROUP BY workspace_id, lower(trim(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dup_inv:
        samples = [f"{r[0]}:{r[1]}" for r in dup_inv[:20]]
        raise RuntimeError(
            "Refusing to normalize workspace_invitations.email: duplicate canonical "
            f"per workspace. Examples (up to 20): {samples}"
        )

    conn.execute(sa.text("UPDATE users SET email = lower(trim(email))"))
    conn.execute(sa.text("UPDATE workspace_invitations SET email = lower(trim(email))"))


def downgrade() -> None:
    # Original casing is not recoverable.
    pass
