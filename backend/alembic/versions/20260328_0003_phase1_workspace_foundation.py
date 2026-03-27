"""phase 1 workspace foundation + ingestion pipeline

Revision ID: 20260328_0003
Revises: 20260327_0002
Create Date: 2026-03-28
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260328_0003"
down_revision: Union[str, None] = "20260327_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "personal_for_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"], unique=False)
    op.create_index("ix_workspaces_personal_for_user_id", "workspaces", ["personal_for_user_id"], unique=True)

    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"], unique=False)
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"], unique=False)
    op.create_index("ix_workspace_members_role_id", "workspace_members", ["role_id"], unique=False)

    op.create_table(
        "workspace_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workspace_invitations_workspace_id", "workspace_invitations", ["workspace_id"], unique=False)
    op.create_index("ix_workspace_invitations_email", "workspace_invitations", ["email"], unique=False)
    op.create_index("ix_workspace_invitations_token", "workspace_invitations", ["token"], unique=True)

    op.add_column("documents", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("documents", sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'ready'")))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("language", sa.String(length=16), nullable=True))
    op.add_column("documents", sa.Column("parser_version", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"], unique=False)
    op.create_index("ix_documents_sha256", "documents", ["sha256"], unique=False)

    op.add_column("chat_sessions", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_chat_sessions_workspace_id", "chat_sessions", ["workspace_id"], unique=False)

    conn = op.get_bind()
    role_ids: dict[str, uuid.UUID] = {}
    for role_name in ("owner", "admin", "member", "viewer"):
        rid = uuid.uuid4()
        role_ids[role_name] = rid
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (id, name, created_at)
                VALUES (:id, :name, now())
                """
            ),
            {"id": str(rid), "name": role_name},
        )

    users = conn.execute(sa.text("SELECT id, email FROM users")).mappings().all()
    now = datetime.now(timezone.utc)
    for u in users:
        workspace_id = uuid.uuid4()
        user_id = str(u["id"])
        email = (u.get("email") or "user").split("@")[0]
        workspace_name = f"{email} personal workspace"
        conn.execute(
            sa.text(
                """
                INSERT INTO workspaces (id, name, owner_user_id, personal_for_user_id, created_at, updated_at)
                VALUES (:id, :name, CAST(:owner_user_id AS uuid), CAST(:personal_for_user_id AS uuid), now(), now())
                """
            ),
            {
                "id": str(workspace_id),
                "name": workspace_name,
                "owner_user_id": user_id,
                "personal_for_user_id": user_id,
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO workspace_members (id, workspace_id, user_id, role_id, created_at)
                VALUES (:id, CAST(:workspace_id AS uuid), CAST(:user_id AS uuid), CAST(:role_id AS uuid), :created_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "workspace_id": str(workspace_id),
                "user_id": user_id,
                "role_id": str(role_ids["owner"]),
                "created_at": now,
            },
        )

        conn.execute(
            sa.text(
                """
                UPDATE documents
                SET workspace_id = CAST(:workspace_id AS uuid)
                WHERE owner_id = CAST(:owner_id AS uuid) AND workspace_id IS NULL
                """
            ),
            {"workspace_id": str(workspace_id), "owner_id": user_id},
        )
        conn.execute(
            sa.text(
                """
                UPDATE chat_sessions
                SET workspace_id = CAST(:workspace_id AS uuid)
                WHERE owner_id = CAST(:owner_id AS uuid) AND workspace_id IS NULL
                """
            ),
            {"workspace_id": str(workspace_id), "owner_id": user_id},
        )

    op.alter_column("documents", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_workspace_id_workspaces",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("chat_sessions", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_chat_sessions_workspace_id_workspaces",
        "chat_sessions",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"], unique=False)
    op.create_index("ix_ingestion_jobs_workspace_id", "ingestion_jobs", ["workspace_id"], unique=False)
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"], unique=False)
    op.create_index("ix_ingestion_jobs_available_at", "ingestion_jobs", ["available_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_available_at", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_workspace_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_document_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    op.drop_constraint("fk_chat_sessions_workspace_id_workspaces", "chat_sessions", type_="foreignkey")
    op.drop_index("ix_chat_sessions_workspace_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "workspace_id")

    op.drop_constraint("fk_documents_workspace_id_workspaces", "documents", type_="foreignkey")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "parser_version")
    op.drop_column("documents", "language")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "sha256")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
    op.drop_column("documents", "workspace_id")

    op.drop_index("ix_workspace_invitations_token", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_email", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_id", table_name="workspace_invitations")
    op.drop_table("workspace_invitations")

    op.drop_index("ix_workspace_members_role_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")

    op.drop_index("ix_workspaces_personal_for_user_id", table_name="workspaces")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
