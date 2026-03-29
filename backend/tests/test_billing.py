"""Router ``/billing`` — usage & ledger (WorkspaceReadAccess)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_billing_usage_happy_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get(
        "/api/v1/billing/usage",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "plan_slug" in body
    assert "usage_requests_month" in body


def test_billing_usage_unauthorized(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get("/api/v1/billing/usage", headers={"X-Workspace-Id": a["ws"]})
    assert r.status_code == 401


def test_billing_usage_foreign_workspace_forbidden(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    r = client.get(
        "/api/v1/billing/usage",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": b["ws"]},
    )
    assert r.status_code == 403
