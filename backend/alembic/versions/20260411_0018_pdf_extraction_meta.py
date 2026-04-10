"""documents: pdf_kind, ocr_applied, extraction_meta for OCR pipeline

Revision ID: 20260411_0018
Revises: 20260411_0017_documents_workspace_sha256_active
Create Date: 2026-04-11

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260411_0018_pdf_extraction_meta"
down_revision = "20260411_0017_documents_workspace_sha256_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("pdf_kind", sa.String(length=32), nullable=True))
    op.add_column(
        "documents",
        sa.Column("ocr_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("documents", sa.Column("extraction_meta", JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("ALTER TABLE documents ALTER COLUMN ocr_applied DROP DEFAULT")


def downgrade() -> None:
    op.drop_column("documents", "extraction_meta")
    op.drop_column("documents", "ocr_applied")
    op.drop_column("documents", "pdf_kind")
