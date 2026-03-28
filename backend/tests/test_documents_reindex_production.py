"""Reindex sync path must not run in production."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.routers import documents as documents_router


class ReindexProductionGuardTests(unittest.TestCase):
    def test_sync_reindex_blocked_in_production(self) -> None:
        db = MagicMock()
        user = MagicMock()
        ws = MagicMock()
        ws.workspace.id = uuid.uuid4()

        with (
            patch.object(documents_router.settings, "ingestion_async_enabled", False),
            patch.object(documents_router.settings, "environment", "production"),
        ):
            with self.assertRaises(HTTPException) as err:
                documents_router.reindex_embeddings(db, user, ws)  # type: ignore[arg-type]
            self.assertEqual(err.exception.status_code, 503)
            self.assertIn("production", (err.exception.detail or "").lower())


if __name__ == "__main__":
    unittest.main()
