"""Router ``/auth`` — register, login, session helpers (no ``X-Workspace-Id`` on these paths)."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_auth_register_happy_path(client: TestClient) -> None:
    email = f"auth_rt_{uuid.uuid4().hex[:16]}@example.com"
    password = "AuthRouteTest1!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Route Test"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email
    assert "id" in body


def test_auth_logout_all_unauthorized(client: TestClient) -> None:
    r = client.post("/api/v1/auth/logout-all")
    assert r.status_code == 401


def test_auth_foreign_workspace_returns_403_not_applicable() -> None:
    pytest.skip(
        "/auth routes do not use X-Workspace-Id. "
        "403 with another tenant's workspace id: see test_billing / test_documents / test_search / test_chat."
    )
