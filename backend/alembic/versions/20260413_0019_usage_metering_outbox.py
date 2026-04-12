"""usage metering outbox + idempotent usage_events

Revision ID: 20260413_0019_usage_outbox
Revises: 20260411_0018_pdf_meta
Create Date: 2026-04-13
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260413_0019_usage_outbox"
down_revision = "20260411_0018_pdf_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_events", sa.Column("idempotency_key", sa.String(length=191), nullable=True))
    op.create_unique_constraint("uq_usage_events_idempotency_key", "usage_events", ["idempotency_key"])

    op.create_table(
        "usage_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
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
        sa.Column("idempotency_key", sa.String(length=191), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_usage_outbox_idempotency_key"),
    )
    op.create_index("ix_usage_outbox_workspace_id", "usage_outbox", ["workspace_id"], unique=False)
    op.create_index("ix_usage_outbox_document_id", "usage_outbox", ["document_id"], unique=False)
    op.create_index("ix_usage_outbox_status_created", "usage_outbox", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_outbox_status_created", table_name="usage_outbox")
    op.drop_index("ix_usage_outbox_document_id", table_name="usage_outbox")
    op.drop_index("ix_usage_outbox_workspace_id", table_name="usage_outbox")
    op.drop_table("usage_outbox")

    op.drop_constraint("uq_usage_events_idempotency_key", "usage_events", type_="unique")
    op.drop_index("ix_usage_events_idempotency_key", table_name="usage_events")
    op.drop_column("usage_events", "idempotency_key")
