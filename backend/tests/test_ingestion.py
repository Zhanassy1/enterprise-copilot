"""Router ``/ingestion`` — ingestion jobs for workspace."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_ingestion_jobs_happy_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get(
        "/api/v1/ingestion/jobs",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_ingestion_jobs_unauthorized(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get("/api/v1/ingestion/jobs", headers={"X-Workspace-Id": a["ws"]})
    assert r.status_code == 401


def test_ingestion_jobs_foreign_workspace_forbidden(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    r = client.get(
        "/api/v1/ingestion/jobs",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": b["ws"]},
    )
    assert r.status_code == 403
