"""Login failure writes audit row (no password in metadata)."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app.api.routers import auth as auth_router
from app.schemas.auth import LoginIn


class LoginFailedAuditTests(unittest.TestCase):
    def test_failed_login_calls_audit_log(self) -> None:
        mock_db = MagicMock()
        mock_db.scalar.return_value = None
        scope = {
            "type": "http",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        payload = LoginIn(email="ghost@example.com", password="wrong")

        with patch.object(auth_router, "write_audit_log") as mock_audit:
            with self.assertRaises(HTTPException) as err:
                auth_router.login(payload, mock_db, request)  # type: ignore[operator]
            self.assertEqual(err.exception.status_code, 401)
            mock_audit.assert_called_once()
            kwargs = mock_audit.call_args.kwargs
            self.assertEqual(kwargs.get("event_type"), "auth.login_failed")
            self.assertEqual(kwargs.get("metadata", {}).get("reason"), "invalid_credentials")
            self.assertIn("ip", kwargs.get("metadata") or {})


if __name__ == "__main__":
    unittest.main()
