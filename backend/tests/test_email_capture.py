"""In-memory email capture (EMAIL_CAPTURE_MODE) — no SMTP."""

import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services import email_service


class EmailCaptureTests(unittest.TestCase):
    def tearDown(self) -> None:
        email_service.clear_captured_emails()

    def test_capture_mode_stores_verification_email(self) -> None:
        with patch.object(settings, "email_capture_mode", True):
            email_service.clear_captured_emails()
            ok = email_service.send_verification_email("u@example.com", "opaque-token-abc")
        self.assertTrue(ok)
        cap = email_service.get_captured_emails()
        self.assertEqual(len(cap), 1)
        self.assertEqual(cap[0]["to"], "u@example.com")
        self.assertIn("opaque-token-abc", cap[0]["body"])
        self.assertIn("Verify", cap[0]["subject"])

    def test_capture_mode_stores_password_reset_email(self) -> None:
        with patch.object(settings, "email_capture_mode", True):
            email_service.clear_captured_emails()
            ok = email_service.send_password_reset_email("u@example.com", "reset-token-xyz")
        self.assertTrue(ok)
        cap = email_service.get_captured_emails()
        self.assertEqual(len(cap), 1)
        self.assertIn("reset-token-xyz", cap[0]["body"])
        self.assertIn("password", cap[0]["subject"].lower())


if __name__ == "__main__":
    unittest.main()
