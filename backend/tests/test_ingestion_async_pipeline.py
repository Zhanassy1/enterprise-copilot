import os
import time
import uuid
import unittest

from fastapi.testclient import TestClient

from app.celery_app import celery_app
from app.core.config import settings
from app.main import app


@unittest.skipUnless(
    os.environ.get("RUN_ASYNC_PIPELINE_SMOKE") == "1",
    "Set RUN_ASYNC_PIPELINE_SMOKE=1 to run async ingestion smoke.",
)
class AsyncIngestionPipelineSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_upload_async_pipeline_reaches_terminal_status(self) -> None:
        email = f"it_async_{uuid.uuid4().hex[:10]}@example.com"
        password = "StrongPass123!"

        original_async = settings.ingestion_async_enabled
        original_always_eager = celery_app.conf.task_always_eager
        original_eager_propagates = celery_app.conf.task_eager_propagates
        settings.ingestion_async_enabled = True
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True
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
            headers = {"Authorization": f"Bearer {token}"}

            upload_res = self.client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("async-contract.txt", b"Amount: 120000 KZT\n", "text/plain")},
            )
            self.assertEqual(upload_res.status_code, 200, upload_res.text)
            self.assertIn(upload_res.json()["document"]["status"], {"queued", "processing", "retrying", "ready", "failed"})

            terminal = None
            for _ in range(10):
                listed = self.client.get("/api/v1/documents", headers=headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                docs = listed.json()
                self.assertTrue(docs)
                terminal = docs[0]["status"]
                if terminal in {"ready", "failed"}:
                    break
                time.sleep(0.2)

            self.assertIn(terminal, {"ready", "failed"})
        finally:
            settings.ingestion_async_enabled = original_async
            celery_app.conf.task_always_eager = original_always_eager
            celery_app.conf.task_eager_propagates = original_eager_propagates


if __name__ == "__main__":
    unittest.main()
