"""document_summary_cache for LLM summaries keyed by parser_version + text hash

Revision ID: 20260425_0022_doc_summary_cache
Revises: 20260421_0021_chunk_fts
Create Date: 2026-04-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260425_0022_doc_summary_cache"
down_revision = "20260421_0021_chunk_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_summary_cache",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("extracted_text_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "parser_version",
            "extracted_text_hash",
            name="uq_document_summary_cache_doc_parser_hash",
        ),
    )
    op.create_index(
        op.f("ix_document_summary_cache_document_id"),
        "document_summary_cache",
        ["document_id"],
        unique=False,
    )
    op.alter_column("document_summary_cache", "parser_version", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_summary_cache_document_id"), table_name="document_summary_cache")
    op.drop_table("document_summary_cache")
