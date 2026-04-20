"""Unit tests for ``DocumentChunkRepository`` (no database)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.repositories.document_chunks import DocumentChunkRepository


class DocumentChunkRepositoryUnitTests(unittest.TestCase):
    def test_bulk_update_embeddings_rejects_length_mismatch(self) -> None:
        repo = DocumentChunkRepository(MagicMock())
        with self.assertRaises(ValueError) as ctx:
            repo.bulk_update_embeddings(
                ["a", "b"],
                [[0.1, 0.2]],
                embedding_dim=2,
            )
        self.assertIn("mismatch", str(ctx.exception).lower())

    def test_bulk_update_embeddings_noop_on_empty_ids(self) -> None:
        db = MagicMock()
        repo = DocumentChunkRepository(db)
        repo.bulk_update_embeddings([], [], embedding_dim=384)
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
