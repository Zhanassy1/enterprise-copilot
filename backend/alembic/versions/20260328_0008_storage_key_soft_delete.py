"""storage_key column rename, soft delete timestamp

Revision ID: 20260328_0008
Revises: 20260328_0007_chunk_citation_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0008"
down_revision = "20260328_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE documents RENAME COLUMN storage_path TO storage_key')
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.execute("ALTER TABLE documents RENAME COLUMN storage_key TO storage_path")
