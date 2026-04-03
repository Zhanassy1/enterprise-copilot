"""Enterprise: platform admin flag, Stripe subscription fields on workspace_quotas."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260403_0010_enterprise"
down_revision = "20260328_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "workspace_quotas",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "workspace_quotas",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "workspace_quotas",
        sa.Column("subscription_status", sa.String(64), nullable=True),
    )
    op.add_column(
        "workspace_quotas",
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workspace_quotas",
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workspace_quotas_stripe_customer_id", "workspace_quotas", ["stripe_customer_id"], unique=False)
    op.create_index(
        "ix_workspace_quotas_stripe_subscription_id", "workspace_quotas", ["stripe_subscription_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_quotas_stripe_subscription_id", table_name="workspace_quotas")
    op.drop_index("ix_workspace_quotas_stripe_customer_id", table_name="workspace_quotas")
    op.drop_column("workspace_quotas", "grace_ends_at")
    op.drop_column("workspace_quotas", "current_period_end")
    op.drop_column("workspace_quotas", "subscription_status")
    op.drop_column("workspace_quotas", "stripe_subscription_id")
    op.drop_column("workspace_quotas", "stripe_customer_id")
    op.drop_column("users", "is_platform_admin")
