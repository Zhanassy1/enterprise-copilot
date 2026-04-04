"""workspace_quotas.trial_ends_at for Stripe trialing display

Revision ID: 20260405_0014
Revises: 20260404_0013
Create Date: 2026-04-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# alembic_version.version_num is VARCHAR(32); keep revision id <= 32 chars.
revision = "20260405_0014_trial_ends"
down_revision = "20260404_0013_workspace_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_quotas",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspace_quotas", "trial_ends_at")
