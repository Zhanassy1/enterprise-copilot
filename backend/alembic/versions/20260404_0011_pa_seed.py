"""Seed is_platform_admin for default dev operator email (aligns with dev compose / .env.docker)."""

from __future__ import annotations

from alembic import op

# revision id must fit alembic_version.version_num VARCHAR(32)
revision = "20260404_0011_pa_seed"
down_revision = "20260403_0010_enterprise"
branch_labels = None
depends_on = None

# Literal dev email — same as PLATFORM_ADMIN_EMAILS in docker-compose / .env.docker
_DEV_EMAIL = "platform-admin@example.invalid"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE users
        SET is_platform_admin = true
        WHERE lower(btrim(email)) = lower(btrim('{_DEV_EMAIL}'))
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE users
        SET is_platform_admin = false
        WHERE lower(btrim(email)) = lower(btrim('{_DEV_EMAIL}'))
        """
    )
