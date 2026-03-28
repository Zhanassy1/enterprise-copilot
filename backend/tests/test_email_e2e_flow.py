"""
Full HTTP e2e: register / request-password-reset → captured body → token → verify-email / reset-password.
Requires PostgreSQL (same as test_api_integration). Run with RUN_INTEGRATION_TESTS=1.
"""

import os
import re
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import email_service


def _extract_query_token(body: str) -> str:
    """Parse token from app_base_url link (?token=...)."""
    m = re.search(r"[?&]token=([^&\s]+)", body)
    if not m:
        raise AssertionError(f"no token= in body: {body[:500]}")
    return m.group(1).strip()


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run email e2e tests.",
)
class EmailE2EFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def tearDown(self) -> None:
        email_service.clear_captured_emails()

    def test_register_verify_then_password_reset_login(self) -> None:
        with patch.object(settings, "email_capture_mode", True):
            email_service.clear_captured_emails()
            uid = uuid.uuid4().hex[:10]
            email = f"e2e_{uid}@example.com"
            password = "E2eOriginal123!"
            new_password = "E2eRenewed456!"

            reg = self.client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "full_name": "E2E Email"},
            )
            self.assertEqual(reg.status_code, 200, reg.text)
            self.assertFalse(reg.json().get("email_verified", True))

            caps = email_service.get_captured_emails()
            self.assertEqual(len(caps), 1, caps)
            self.assertEqual(caps[0]["to"], email)
            verify_token = _extract_query_token(caps[0]["body"])

            ver = self.client.post("/api/v1/auth/verify-email", json={"token": verify_token})
            self.assertEqual(ver.status_code, 200, ver.text)
            self.assertTrue(ver.json().get("ok"))

            email_service.clear_captured_emails()
            req = self.client.post("/api/v1/auth/request-password-reset", json={"email": email})
            self.assertEqual(req.status_code, 200, req.text)
            self.assertTrue(req.json().get("ok"))

            caps2 = email_service.get_captured_emails()
            self.assertEqual(len(caps2), 1, caps2)
            reset_token = _extract_query_token(caps2[0]["body"])

            reset = self.client.post(
                "/api/v1/auth/reset-password",
                json={"token": reset_token, "new_password": new_password},
            )
            self.assertEqual(reset.status_code, 200, reset.text)
            self.assertTrue(reset.json().get("ok"))

            bad = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
            self.assertEqual(bad.status_code, 401, bad.text)

            ok = self.client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
            self.assertEqual(ok.status_code, 200, ok.text)
            self.assertIn("access_token", ok.json())


if __name__ == "__main__":
    unittest.main()
