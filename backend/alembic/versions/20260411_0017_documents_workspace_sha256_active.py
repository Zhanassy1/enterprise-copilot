"""Partial unique index: workspace + sha256 for active document pipeline rows

Revision ID: 20260411_0017_doc_ws_sha256
Revises: 20260410_0016_email_lower
Create Date: 2026-04-11

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260411_0017_doc_ws_sha256"
down_revision = "20260410_0016_email_lower"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM documents
            WHERE deleted_at IS NULL
              AND sha256 IS NOT NULL
              AND status IN ('queued', 'processing', 'retrying', 'ready')
            GROUP BY workspace_id, sha256
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    if row is not None:
        raise RuntimeError(
            "Refusing to create uq_documents_workspace_sha256_active: duplicate "
            "(workspace_id, sha256) exists for active pipeline rows. Resolve duplicates first."
        )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_documents_workspace_sha256_active
            ON documents (workspace_id, sha256)
            WHERE deleted_at IS NULL
              AND sha256 IS NOT NULL
              AND status IN ('queued', 'processing', 'retrying', 'ready')
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_documents_workspace_sha256_active"))
