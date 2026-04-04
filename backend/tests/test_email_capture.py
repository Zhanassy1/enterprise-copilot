"""In-memory email capture (EMAIL_CAPTURE_MODE) — no SMTP."""

import unittest
from unittest.mock import MagicMock, patch

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

    def test_sendgrid_api_used_when_key_set(self) -> None:
        email_service.clear_captured_emails()
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.text = ""
        with (
            patch.object(settings, "email_capture_mode", False),
            patch.object(settings, "sendgrid_api_key", "SG.test-key"),
            patch.object(settings, "smtp_host", ""),
            patch.object(settings, "smtp_from_email", "from@example.com"),
            patch("app.services.email_service.httpx.post", return_value=mock_resp) as post,
        ):
            ok = email_service.send_email(to_email="u@example.com", subject="Hi", body="Body")
        self.assertTrue(ok)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertIn("sendgrid.com", args[0])


if __name__ == "__main__":
    unittest.main()
