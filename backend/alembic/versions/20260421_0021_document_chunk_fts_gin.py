"""document_chunks: stored tsvector + chunk_search_aux + GIN indexes

Revision ID: 20260421_0021_chunk_fts
Revises: 20260415_0020_drop_emb
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260421_0021_chunk_fts"
down_revision = "20260415_0020_drop_emb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("chunk_search_aux", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("document_chunks", "chunk_search_aux", server_default=None)

    op.execute(
        sa.text(
            """
            ALTER TABLE document_chunks ADD COLUMN chunk_tsv_ru tsvector
              GENERATED ALWAYS AS (to_tsvector('russian', COALESCE(text, ''))) STORED
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE document_chunks ADD COLUMN chunk_tsv_simple tsvector
              GENERATED ALWAYS AS (to_tsvector('simple', COALESCE(text, ''))) STORED
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE document_chunks ADD COLUMN chunk_tsv_aux tsvector
              GENERATED ALWAYS AS (to_tsvector('simple', COALESCE(chunk_search_aux, ''))) STORED
            """
        )
    )

    op.execute(
        sa.text(
            "CREATE INDEX ix_document_chunks_chunk_tsv_ru ON document_chunks USING gin (chunk_tsv_ru)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_document_chunks_chunk_tsv_simple ON document_chunks USING gin (chunk_tsv_simple)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_document_chunks_chunk_tsv_aux ON document_chunks USING gin (chunk_tsv_aux)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_chunk_tsv_aux"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_chunk_tsv_simple"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_chunk_tsv_ru"))
    op.execute(sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_tsv_aux"))
    op.execute(sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_tsv_simple"))
    op.execute(sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_tsv_ru"))
    op.drop_column("document_chunks", "chunk_search_aux")
