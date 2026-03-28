"""plan slug, document cap, billing ledger

Revision ID: 20260328_0009
Revises: 20260328_0008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260328_0009"
down_revision: Union[str, None] = "20260328_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    q = sa.text(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
        """
    )
    return conn.execute(q, {"t": table, "c": column}).scalar() is not None


def _has_table(table: str) -> bool:
    conn = op.get_bind()
    q = sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return conn.execute(q, {"t": table}).scalar() is not None


def _has_index(index_name: str) -> bool:
    conn = op.get_bind()
    q = sa.text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :i")
    return conn.execute(q, {"i": index_name}).scalar() is not None


def upgrade() -> None:
    if not _has_column("workspace_quotas", "plan_slug"):
        op.add_column(
            "workspace_quotas",
            sa.Column("plan_slug", sa.String(length=32), nullable=False, server_default="free"),
        )
    if not _has_column("workspace_quotas", "max_documents"):
        op.add_column(
            "workspace_quotas",
            sa.Column("max_documents", sa.BigInteger(), nullable=True),
        )
    if not _has_table("billing_ledger_entries"):
        op.create_table(
            "billing_ledger_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_id", sa.String(length=191), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'USD'")),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("external_id", name="uq_billing_ledger_external_id"),
        )
    if not _has_index("ix_billing_ledger_workspace_id"):
        op.create_index("ix_billing_ledger_workspace_id", "billing_ledger_entries", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_billing_ledger_workspace_id", table_name="billing_ledger_entries")
    op.drop_table("billing_ledger_entries")
    op.drop_column("workspace_quotas", "max_documents")
    op.drop_column("workspace_quotas", "plan_slug")
