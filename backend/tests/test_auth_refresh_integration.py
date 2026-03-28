"""Auth refresh rotation, logout, reuse detection — requires PostgreSQL + migrations."""

import os
import unittest
import uuid

from fastapi.testclient import TestClient

from app.main import app


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class AuthRefreshIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_refresh_rotate_and_reuse_revokes_family(self) -> None:
        email = f"rt_{uuid.uuid4().hex[:10]}@example.com"
        password = "StrongPass123!"
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "RT"},
        )
        login = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        self.assertEqual(login.status_code, 200, login.text)
        rt1 = login.json()["refresh_token"]
        ref1 = self.client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        self.assertEqual(ref1.status_code, 200, ref1.text)
        rt2 = ref1.json()["refresh_token"]
        reuse = self.client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
        self.assertEqual(reuse.status_code, 401, reuse.text)
        after_reuse = self.client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
        self.assertEqual(after_reuse.status_code, 401, after_reuse.text)


if __name__ == "__main__":
    unittest.main()
