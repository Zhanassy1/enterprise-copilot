"""Workspace invitations API."""

from __future__ import annotations

import os
import re
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
    created = r.json()
    inv_id = created["id"]
    assert created.get("plain_token") and len(str(created["plain_token"])) >= 16

    li = client.get(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert li.status_code == 200
    assert any(x["email"] == invite_email for x in li.json())

    caps = email_service.get_captured_emails()
    assert caps, "invite email should be captured"
    body = caps[-1].get("body") or ""
    assert "/invite/" in body
    assert "invite?token=" not in body

    rv = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations/{inv_id}/revoke",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert rv.status_code == 200, rv.text


def _plain_token_from_invite_email_body(body: str) -> str:
    m = re.search(r"/invite/([^/\s<>\"'&]+)", body)
    if m:
        return m.group(1)
    m = re.search(r"invite\?token=([^&\s<>\"']+)", body)
    assert m, "token in email body"
    return m.group(1)


def test_invite_register_via_auth_clears_token(client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "email_capture_mode", True)
    from app.services import email_service

    email_service.clear_captured_emails()

    a = two_workspaces["a"]
    invite_email = f"inv_new_{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        json={"email": invite_email, "role": "member"},
    )
    assert r.status_code == 200, r.text
    caps = email_service.get_captured_emails()
    body = caps[-1].get("body") or ""
    plain = _plain_token_from_invite_email_body(body)

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": invite_email,
            "password": "EightChr1!",
            "full_name": "Invited",
            "invite_token": plain,
        },
    )
    assert reg.status_code == 200, reg.text
    assert "access_token" in reg.json()

    bad = client.get(f"/api/v1/invitations/validate?token={plain}")
    assert bad.status_code == 400


def test_invite_login_existing_user_with_invite_token(client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "email_capture_mode", True)
    from app.services import email_service

    email_service.clear_captured_emails()

    a = two_workspaces["a"]
    b = two_workspaces["b"]
    pwd = "PytestRouterSuite1!"
    r = client.post(
        f"/api/v1/workspaces/{a['ws']}/invitations",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        json={"email": b["email"], "role": "member"},
    )
    assert r.status_code == 200, r.text
    caps = email_service.get_captured_emails()
    body = caps[-1].get("body") or ""
    plain = _plain_token_from_invite_email_body(body)

    li = client.post(
        "/api/v1/auth/login",
        json={"email": b["email"], "password": pwd, "invite_token": plain},
    )
    assert li.status_code == 200, li.text
    assert "access_token" in li.json()

    bad = client.get(f"/api/v1/invitations/validate?token={plain}")
    assert bad.status_code == 400
