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


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    q = sa.text(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
        """
    )
    return conn.execute(q, {"t": table, "c": column}).scalar() is not None


def _has_index(index_name: str) -> bool:
    conn = op.get_bind()
    q = sa.text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :i")
    return conn.execute(q, {"i": index_name}).scalar() is not None


def upgrade() -> None:
    if _has_column("documents", "storage_path") and not _has_column("documents", "storage_key"):
        op.execute(sa.text("ALTER TABLE documents RENAME COLUMN storage_path TO storage_key"))
    if not _has_column("documents", "deleted_at"):
        op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_index("ix_documents_deleted_at"):
        op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.execute("ALTER TABLE documents RENAME COLUMN storage_key TO storage_path")
