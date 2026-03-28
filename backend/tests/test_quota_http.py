"""HTTP-level contract tests for quota / rate-limit responses (no live DB required where mocked)."""

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app.api.deps import WorkspaceContext, get_current_user, get_workspace_context
from app.core.config import settings
from app.db.session import get_db
from app.main import app


def _api_v1_subapp():
    for r in app.routes:
        if isinstance(r, Mount) and r.path == settings.api_v1_prefix:
            return r.app
    raise RuntimeError("API v1 mount not found")


class QuotaHttpTests(unittest.TestCase):
    def tearDown(self) -> None:
        sub = _api_v1_subapp()
        sub.dependency_overrides.clear()

    def test_search_returns_429_when_quota_blocks(self) -> None:
        ws = SimpleNamespace(id=uuid.uuid4(), name="T")
        mem = SimpleNamespace(role=SimpleNamespace(name="member"), workspace_id=ws.id)
        ctx = WorkspaceContext(workspace=ws, membership=mem)

        def fake_user() -> SimpleNamespace:
            return SimpleNamespace(id=uuid.uuid4(), email="x@y.z")

        def fake_db():
            yield MagicMock()

        sub = _api_v1_subapp()
        sub.dependency_overrides[get_current_user] = fake_user
        sub.dependency_overrides[get_workspace_context] = lambda: ctx
        sub.dependency_overrides[get_db] = fake_db

        with patch(
            "app.services.usage_metering.assert_quota",
            side_effect=HTTPException(status_code=429, detail="Workspace monthly request quota exceeded"),
        ):
            with TestClient(app) as client:
                r = client.post(
                    f"{settings.api_v1_prefix}/search",
                    json={"query": "price", "top_k": 3},
                    headers={"Authorization": "Bearer " + "t" * 32},
                )
        self.assertEqual(r.status_code, 429)
        self.assertIn("quota", (r.json().get("detail") or "").lower())


if __name__ == "__main__":
    unittest.main()
