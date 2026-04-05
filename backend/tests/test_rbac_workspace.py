"""RBAC integration: billing and writes restricted by workspace role (PostgreSQL)."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services.workspace_service import ensure_default_roles

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def _add_membership(
    *,
    workspace_id: uuid.UUID,
    user_email: str,
    role_key: str,
) -> None:
    db = SessionLocal()
    try:
        roles = ensure_default_roles(db)
        role = roles.get(role_key)
        assert role is not None
        user = db.scalar(select(User).where(User.email == user_email))
        assert user is not None
        existing = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if existing:
            existing.role_id = role.id
        else:
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    user_id=user.id,
                    role_id=role.id,
                )
            )
        db.commit()
    finally:
        db.close()


def test_billing_usage_403_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.get(
        "/api/v1/billing/usage",
        headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 403, r.text


def test_billing_subscription_200_for_member_and_viewer(client: TestClient, two_workspaces: dict) -> None:
    """Subscription status + dunning banner are visible to all workspace roles (read)."""
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    for role_key in ("member", "viewer"):
        _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key=role_key)
        r = client.get(
            "/api/v1/billing/subscription",
            headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("banner_variant") in ("none", "warning", "critical")
        assert "past_due_banner" in body


def test_billing_invoices_403_for_member(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="member")
    r = client.get(
        "/api/v1/billing/invoices",
        headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 403, r.text


def test_chat_create_session_403_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.post(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
        json={"title": "x"},
    )
    assert r.status_code == 403, r.text


def test_invite_create_403_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {b['token']}"},
        json={"email": "someone_else@example.com", "role": "member"},
    )
    assert r.status_code == 403, r.text


def test_invite_list_200_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    """Pending invitations list is readable by all workspace members."""
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.get(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
