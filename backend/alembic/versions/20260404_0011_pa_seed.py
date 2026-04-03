"""Placeholder revision (no PII). Grant platform admin via PLATFORM_ADMIN_EMAILS or users.is_platform_admin."""

from __future__ import annotations

from alembic import op

# revision id must fit alembic_version.version_num VARCHAR(32)
revision = "20260404_0011_pa_seed"
down_revision = "20260403_0010_enterprise"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Intentionally empty: do not seed real emails in a public repo. Use env or SQL locally."""
    pass


def downgrade() -> None:
    pass
