"""add chunk citation metadata

Revision ID: 20260328_0007
Revises: 20260328_0006
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260328_0007"
down_revision: Union[str, None] = "20260328_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("page_number", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("paragraph_index", sa.Integer(), nullable=True))
    op.create_index("ix_document_chunks_page_number", "document_chunks", ["page_number"], unique=False)
    op.create_index("ix_document_chunks_paragraph_index", "document_chunks", ["paragraph_index"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_chunks_paragraph_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_page_number", table_name="document_chunks")
    op.drop_column("document_chunks", "paragraph_index")
    op.drop_column("document_chunks", "page_number")
