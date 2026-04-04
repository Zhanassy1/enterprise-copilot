"""Workspace members list and mutations (PostgreSQL integration)."""

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


def test_list_members_200_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {b['token']}"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    emails = {row["email"] for row in rows}
    assert b["email"] in emails


def test_list_members_200_with_slug_in_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    wr = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {a['token']}"})
    assert wr.status_code == 200, wr.text
    slug = wr.json()[0]["slug"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.get(
        f"/api/v1/workspaces/{slug}/members",
        headers={"Authorization": f"Bearer {b['token']}"},
    )
    assert r.status_code == 200, r.text
    emails = {row["email"] for row in r.json()}
    assert b["email"] in emails


def test_patch_member_403_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r0 = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    assert r0.status_code == 200, r0.text
    bid = next(row["user_id"] for row in r0.json() if row["email"] == b["email"])
    r = client.patch(
        f"/api/v1/workspaces/{a['ws']}/members/{bid}",
        headers={"Authorization": f"Bearer {b['token']}"},
        json={"role": "member"},
    )
    assert r.status_code == 403, r.text


def test_patch_member_403_for_member(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="member")
    r0 = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    bid = next(row["user_id"] for row in r0.json() if row["email"] == b["email"])
    r = client.patch(
        f"/api/v1/workspaces/{a['ws']}/members/{bid}",
        headers={"Authorization": f"Bearer {b['token']}"},
        json={"role": "viewer"},
    )
    assert r.status_code == 403, r.text


def test_owner_can_patch_member_role(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="member")
    r0 = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    bid = next(row["user_id"] for row in r0.json() if row["email"] == b["email"])
    r = client.patch(
        f"/api/v1/workspaces/{a['ws']}/members/{bid}",
        headers={"Authorization": f"Bearer {a['token']}"},
        json={"role": "viewer"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "viewer"


def test_admin_cannot_patch_owner(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="admin")
    r0 = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    # workspace owner (user A) has role owner — find their user id
    aid = next(row["user_id"] for row in r0.json() if row["email"] == a["email"])
    r = client.patch(
        f"/api/v1/workspaces/{a['ws']}/members/{aid}",
        headers={"Authorization": f"Bearer {b['token']}"},
        json={"role": "member"},
    )
    assert r.status_code == 403, r.text


def test_delete_member_403_for_viewer(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r0 = client.get(
        f"/api/v1/workspaces/{a['ws']}/members",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    bid = next(row["user_id"] for row in r0.json() if row["email"] == b["email"])
    r = client.delete(
        f"/api/v1/workspaces/{a['ws']}/members/{bid}",
        headers={"Authorization": f"Bearer {b['token']}"},
    )
    assert r.status_code == 403, r.text
