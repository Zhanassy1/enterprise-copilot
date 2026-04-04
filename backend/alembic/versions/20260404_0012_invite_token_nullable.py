"""Workspace invitation token cleared after accept/revoke (nullable)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260404_0012_invite"
down_revision = "20260404_0011_pa_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "workspace_invitations",
        "token",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE workspace_invitations SET token = "
            "md5(random()::text || id::text || clock_timestamp()::text || random()::text) || "
            "md5(gen_random_uuid()::text) "
            "WHERE token IS NULL"
        )
    )
    op.alter_column(
        "workspace_invitations",
        "token",
        existing_type=sa.String(length=255),
        nullable=False,
    )
