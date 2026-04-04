"""Workspace slug column (unique index, backfill from name)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.workspace_slug import slugify_name

revision = "20260404_0013_workspace_slug"
down_revision = "20260404_0012_invite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("slug", sa.String(length=64), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, name FROM workspaces")).fetchall()
    used_slugs: set[str] = set()
    for rid, name in rows:
        base = slugify_name(str(name) if name else "workspace")
        cand = base
        n = 0
        while cand in used_slugs:
            n += 1
            cand = f"{base[:50]}-{n}"[:64]
        used_slugs.add(cand)
        conn.execute(
            sa.text("UPDATE workspaces SET slug = :slug WHERE id = :id"),
            {"slug": cand, "id": rid},
        )
    op.alter_column("workspaces", "slug", existing_type=sa.String(length=64), nullable=False)
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_column("workspaces", "slug")
