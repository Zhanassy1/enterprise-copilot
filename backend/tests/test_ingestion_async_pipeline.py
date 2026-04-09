import os

# Celery should load with eager=True before app import when this file is the only test module (async-smoke CI job).
if os.environ.get("RUN_ASYNC_PIPELINE_SMOKE") == "1":
    os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
    os.environ.setdefault("CELERY_TASK_EAGER_PROPAGATES", "1")
    os.environ.setdefault("SQLALCHEMY_USE_NULLPOOL", "1")

import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.celery_app import celery_app
from app.core.config import settings
from app.main import app
from app.tasks.ingestion import ingest_document_task


@unittest.skipUnless(
    os.environ.get("RUN_ASYNC_PIPELINE_SMOKE") == "1",
    "Set RUN_ASYNC_PIPELINE_SMOKE=1 to run async ingestion smoke.",
)
class AsyncIngestionPipelineSmokeTests(unittest.TestCase):
    """Upload commits doc+job before enqueue (see document_ingestion). In full discover, patch apply_async→apply if Celery was imported without eager."""

    _apply_async_patch = None

    @classmethod
    def setUpClass(cls) -> None:
        def _apply_kwargs(**opts: object) -> object:
            inner = opts.get("kwargs")
            if not isinstance(inner, dict):
                raise AssertionError("expected kwargs= for ingest_document_task.apply_async")
            r = ingest_document_task.apply(kwargs=inner)
            if getattr(r, "failed", lambda: False)():
                raise AssertionError(f"ingest_document_task failed: {getattr(r, 'result', r)}")
            return r

        if not celery_app.conf.task_always_eager:
            p = patch(
                "app.services.document_ingestion.ingest_document_task.apply_async",
                side_effect=_apply_kwargs,
            )
            p.start()
            cls._apply_async_patch = p
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        if getattr(cls, "_apply_async_patch", None) is not None:
            cls._apply_async_patch.stop()

    def _headers_with_workspace(self, access_token: str) -> dict[str, str]:
        h = {"Authorization": f"Bearer {access_token}"}
        ws_res = self.client.get("/api/v1/workspaces", headers=h)
        self.assertEqual(ws_res.status_code, 200, ws_res.text)
        workspaces = ws_res.json()
        self.assertGreaterEqual(len(workspaces), 1, ws_res.text)
        h["X-Workspace-Id"] = str(workspaces[0]["id"])
        return h

    def test_upload_async_pipeline_reaches_terminal_status(self) -> None:
        email = f"it_async_{uuid.uuid4().hex[:10]}@example.com"
        password = "StrongPass123!"

        original_async = settings.ingestion_async_enabled
        settings.ingestion_async_enabled = True
        try:
            register_res = self.client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "full_name": "Async Integration User"},
            )
            self.assertEqual(register_res.status_code, 200, register_res.text)

            login_res = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            self.assertEqual(login_res.status_code, 200, login_res.text)
            token = login_res.json()["access_token"]
            headers = self._headers_with_workspace(token)

            upload_res = self.client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("async-contract.txt", b"Amount: 120000 KZT\n", "text/plain")},
            )
            self.assertEqual(upload_res.status_code, 200, upload_res.text)
            self.assertIn(upload_res.json()["document"]["status"], {"queued", "processing", "retrying", "ready", "failed"})

            terminal = None
            for _ in range(180):
                listed = self.client.get("/api/v1/documents", headers=headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                docs = listed.json()
                self.assertTrue(docs)
                terminal = docs[0]["status"]
                if terminal in {"ready", "failed"}:
                    break
                time.sleep(0.5)

            self.assertIn(terminal, {"ready", "failed"})
        finally:
            settings.ingestion_async_enabled = original_async

    def test_upload_increments_billing_usage_after_success(self) -> None:
        """Second commit persists usage rows; billing/usage aggregates reflect document_upload + upload_bytes."""
        email = f"it_usage_{uuid.uuid4().hex[:10]}@example.com"
        password = "StrongPass123!"
        file_body = b"Usage smoke line\n"
        original_async = settings.ingestion_async_enabled
        settings.ingestion_async_enabled = True
        try:
            register_res = self.client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "full_name": "Usage Smoke User"},
            )
            self.assertEqual(register_res.status_code, 200, register_res.text)
            login_res = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            self.assertEqual(login_res.status_code, 200, login_res.text)
            token = login_res.json()["access_token"]
            headers = self._headers_with_workspace(token)

            before = self.client.get("/api/v1/billing/usage", headers=headers)
            self.assertEqual(before.status_code, 200, before.text)
            bj = before.json()

            upload_res = self.client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("usage-smoke.txt", file_body, "text/plain")},
            )
            self.assertEqual(upload_res.status_code, 200, upload_res.text)

            after = self.client.get("/api/v1/billing/usage", headers=headers)
            self.assertEqual(after.status_code, 200, after.text)
            aj = after.json()

            self.assertGreaterEqual(aj["usage_bytes_month"], bj["usage_bytes_month"] + len(file_body))
            self.assertGreaterEqual(aj["usage_requests_month"], bj["usage_requests_month"] + 1)
            self.assertGreaterEqual(aj["document_count"], bj["document_count"] + 1)
        finally:
            settings.ingestion_async_enabled = original_async


if __name__ == "__main__":
    unittest.main()
