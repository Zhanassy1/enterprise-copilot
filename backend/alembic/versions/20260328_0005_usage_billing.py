"""phase4 usage events and quotas

Revision ID: 20260328_0005
Revises: 20260328_0004
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260328_0005"
down_revision: Union[str, None] = "20260328_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("monthly_request_limit", sa.Integer(), nullable=False, server_default=sa.text("20000")),
        sa.Column("monthly_token_limit", sa.BigInteger(), nullable=False, server_default=sa.text("20000000")),
        sa.Column("monthly_upload_bytes_limit", sa.BigInteger(), nullable=False, server_default=sa.text("1073741824")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_quotas_workspace_id"),
    )
    op.create_index("ix_workspace_quotas_workspace_id", "workspace_quotas", ["workspace_id"], unique=False)

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default=sa.text("'count'")),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_usage_events_workspace_id", "usage_events", ["workspace_id"], unique=False)
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"], unique=False)
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"], unique=False)
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"], unique=False)

    op.execute(
        """
        INSERT INTO workspace_quotas (id, workspace_id, monthly_request_limit, monthly_token_limit, monthly_upload_bytes_limit, created_at, updated_at)
        SELECT w.id, w.id, 20000, 20000000, 1073741824, now(), now()
        FROM workspaces w
        WHERE NOT EXISTS (
            SELECT 1 FROM workspace_quotas q WHERE q.workspace_id = w.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_event_type", table_name="usage_events")
    op.drop_index("ix_usage_events_user_id", table_name="usage_events")
    op.drop_index("ix_usage_events_workspace_id", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_workspace_quotas_workspace_id", table_name="workspace_quotas")
    op.drop_table("workspace_quotas")
