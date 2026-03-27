"""phase2 celery ingestion runtime

Revision ID: 20260328_0004
Revises: 20260328_0003
Create Date: 2026-03-28 00:00:04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260328_0004"
down_revision = "20260328_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ingestion_jobs",
        "status",
        existing_type=sa.String(length=32),
        server_default=sa.text("'queued'"),
        existing_nullable=False,
    )
    op.add_column("ingestion_jobs", sa.Column("deduplication_key", sa.String(length=191), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("celery_task_id", sa.String(length=191), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("retry_after_seconds", sa.Integer(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE ingestion_jobs SET deduplication_key = id::text WHERE deduplication_key IS NULL")
    op.alter_column("ingestion_jobs", "deduplication_key", existing_type=sa.String(length=191), nullable=False)
    op.create_index("ix_ingestion_jobs_deduplication_key", "ingestion_jobs", ["deduplication_key"], unique=True)
    op.create_index("ix_ingestion_jobs_celery_task_id", "ingestion_jobs", ["celery_task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_celery_task_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_deduplication_key", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "dead_lettered_at")
    op.drop_column("ingestion_jobs", "last_retry_at")
    op.drop_column("ingestion_jobs", "retry_after_seconds")
    op.drop_column("ingestion_jobs", "celery_task_id")
    op.drop_column("ingestion_jobs", "deduplication_key")
    op.alter_column(
        "ingestion_jobs",
        "status",
        existing_type=sa.String(length=32),
        server_default=sa.text("'pending'"),
        existing_nullable=False,
    )
