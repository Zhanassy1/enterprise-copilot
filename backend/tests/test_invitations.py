"""Workspace invitations API."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_invitations_create_list_revoke_flow(client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "email_capture_mode", True)
    from app.services import email_service

    email_service.clear_captured_emails()

    a = two_workspaces["a"]
    invite_email = f"inv_{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        json={"email": invite_email, "role": "member"},
    )
    assert r.status_code == 200, r.text
    inv_id = r.json()["id"]

    li = client.get(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert li.status_code == 200
    assert any(x["email"] == invite_email for x in li.json())

    caps = email_service.get_captured_emails()
    assert caps, "invite email should be captured"
    body = caps[-1].get("body") or ""
    assert "invite?token=" in body

    rv = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations/{inv_id}/revoke",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert rv.status_code == 200, rv.text
