"""reset_password must revoke refresh tokens — app/api/routers/auth.py db.execute(update(RefreshToken)...)."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.api.routers import auth as auth_router
from app.schemas.auth import PasswordResetIn


class PasswordResetRevokesRefreshTests(unittest.TestCase):
    def test_reset_password_calls_execute_to_revoke_refresh_tokens(self) -> None:
        uid = uuid.uuid4()
        token_row = MagicMock()
        token_row.user_id = uid
        token_row.expires_at = datetime.now(UTC) + timedelta(hours=1)
        user = MagicMock()
        user.id = uid
        user.password_hash = "old"

        mock_db = MagicMock()
        mock_db.scalar.side_effect = [token_row, user]

        with (
            patch.object(auth_router, "hash_opaque_token", return_value="h"),
            patch.object(auth_router, "hash_password", return_value="newhash"),
            patch.object(auth_router, "write_audit_log"),
        ):
            auth_router.reset_password(PasswordResetIn(token="opaque", new_password="NewPass12345!"), mock_db)  # type: ignore[arg-type]

        mock_db.execute.assert_called_once()
        # app/api/routers/auth.py: db.execute(update(RefreshToken).where(...).values(revoked=True))
        self.assertIn("revoked", str(mock_db.execute.call_args[0][0]).lower())


if __name__ == "__main__":
    unittest.main()
