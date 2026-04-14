"""drop legacy document_chunks.embedding text column

Revision ID: 20260415_0020_drop_emb
Revises: 20260413_0019_usage_outbox
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260415_0020_drop_emb"
down_revision = "20260413_0019_usage_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("document_chunks", "embedding")


def downgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding", sa.Text(), nullable=True))
