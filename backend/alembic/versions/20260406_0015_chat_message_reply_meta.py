"""chat_messages.reply_meta_json for assistant reply metadata

Revision ID: 20260406_0015
Revises: 20260405_0014_trial_ends
Create Date: 2026-04-06

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260406_0015_reply_meta"
down_revision = "20260405_0014_trial_ends"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("reply_meta_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "reply_meta_json")
