"""Router ``/workspaces`` — list memberships (CurrentUser only, no workspace header)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_workspaces_list_happy_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {a['token']}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    ids = {str(row["id"]) for row in data}
    assert a["ws"] in ids


def test_workspaces_list_unauthorized(client: TestClient) -> None:
    r = client.get("/api/v1/workspaces")
    assert r.status_code == 401


def test_workspaces_foreign_workspace_returns_403_not_applicable() -> None:
    pytest.skip(
        "GET /workspaces ignores X-Workspace-Id (no WorkspaceReadAccess). "
        "403 for another tenant's workspace id: see test_billing / test_documents / test_search / test_chat."
    )
