"""Router ``/search`` — semantic search."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_search_happy_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.post(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        json={"query": "contract", "top_k": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "hits" in body
    assert body["decision"] in ("answer", "clarify", "insufficient_context")


def test_search_unauthorized(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.post(
        "/api/v1/search",
        headers={"X-Workspace-Id": a["ws"]},
        json={"query": "contract", "top_k": 3},
    )
    assert r.status_code == 401


def test_search_foreign_workspace_forbidden(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    r = client.post(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": b["ws"]},
        json={"query": "contract", "top_k": 3},
    )
    assert r.status_code == 403
