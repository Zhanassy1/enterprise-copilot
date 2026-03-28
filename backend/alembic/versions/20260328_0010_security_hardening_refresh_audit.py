"""refresh token chain + audit request metadata

Revision ID: 20260328_0010
Revises: 20260328_0009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260328_0010"
down_revision: Union[str, None] = "20260328_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("jti", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("refresh_tokens", sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE refresh_tokens SET jti = gen_random_uuid() WHERE jti IS NULL"))

    op.alter_column("refresh_tokens", "jti", nullable=False)
    op.create_unique_constraint("uq_refresh_tokens_jti", "refresh_tokens", ["jti"])
    op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"])
    op.create_foreign_key(
        "fk_refresh_tokens_rotated_from_id",
        "refresh_tokens",
        "refresh_tokens",
        ["rotated_from_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("audit_logs", sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.create_foreign_key(
        "fk_audit_logs_actor_user_id",
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_actor_user_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "actor_user_id")

    op.drop_constraint("fk_refresh_tokens_rotated_from_id", "refresh_tokens", type_="foreignkey")
    op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
    op.drop_constraint("uq_refresh_tokens_jti", "refresh_tokens", type_="unique")
    op.drop_column("refresh_tokens", "revoked_at")
    op.drop_column("refresh_tokens", "rotated_from_id")
    op.drop_column("refresh_tokens", "jti")
