"""
Shared pytest fixtures for API router tests (PostgreSQL integration).

Router-focused modules (``test_<router>.py``) cover happy / 401 / 403 paths for
workspace-scoped APIs. Routers ``auth`` and ``workspaces`` have no
``WorkspaceReadAccess`` routes, so their third test is ``pytest.skip`` with a
pointer to scoped routers.

Run: ``RUN_INTEGRATION_TESTS=1 pytest tests/test_billing.py tests/test_billing_stripe_integration.py -v`` (from ``backend/``).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

# Importing ``app`` instantiates ``Settings()`` once. Integration jobs have no Celery/Redis;
# sync indexing must be allowed before that import (env vars in ``test_api_integration`` run too late).
# Use assignment (not setdefault): repo/org Actions variables must not leave ALLOW_SYNC_INGESTION_FOR_DEV=0.
# Async pipeline smoke (``RUN_ASYNC_PIPELINE_SMOKE=1``) keeps async flags from the environment.
if os.environ.get("RUN_INTEGRATION_TESTS") == "1" and os.environ.get("RUN_ASYNC_PIPELINE_SMOKE") != "1":
    os.environ["INGESTION_ASYNC_ENABLED"] = "0"
    os.environ["ALLOW_SYNC_INGESTION_FOR_DEV"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def two_workspaces(client: TestClient) -> dict[str, dict[str, str]]:
    """
    Two users with separate personal workspaces (no cross-membership).
    Keys: ``a`` and ``b`` with ``token`` (JWT) and ``ws`` (workspace id string).
    """
    pwd = "PytestRouterSuite1!"
    ea = f"rt_{uuid.uuid4().hex[:12]}_a@example.com"
    eb = f"rt_{uuid.uuid4().hex[:12]}_b@example.com"

    ra = client.post(
        "/api/v1/auth/register",
        json={"email": ea, "password": pwd, "full_name": "User A"},
    )
    assert ra.status_code == 200, ra.text
    rb = client.post(
        "/api/v1/auth/register",
        json={"email": eb, "password": pwd, "full_name": "User B"},
    )
    assert rb.status_code == 200, rb.text

    la = client.post("/api/v1/auth/login", json={"email": ea, "password": pwd})
    assert la.status_code == 200, la.text
    lb = client.post("/api/v1/auth/login", json={"email": eb, "password": pwd})
    assert lb.status_code == 200, lb.text

    ta = la.json()["access_token"]
    tb = lb.json()["access_token"]

    wa = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {ta}"})
    assert wa.status_code == 200, wa.text
    wb = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {tb}"})
    assert wb.status_code == 200, wb.text
    wsa = wa.json()
    wsb = wb.json()
    assert len(wsa) >= 1 and len(wsb) >= 1

    return {
        "a": {"token": ta, "ws": str(wsa[0]["id"]), "email": ea},
        "b": {"token": tb, "ws": str(wsb[0]["id"]), "email": eb},
    }
