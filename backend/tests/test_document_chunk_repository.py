"""Unit tests for ``DocumentChunkRepository`` (no database)."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock, patch

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

    def test_keyword_candidates_sql_uses_stored_tsv_and_match(self) -> None:
        db = MagicMock()
        db.execute.return_value.mappings.return_value = iter([])
        repo = DocumentChunkRepository(db)
        with patch(
            "app.repositories.document_chunks.prepare_keyword_tsquery_texts",
            return_value=("ru_q", "si_q", "ax_q"),
        ):
            repo.keyword_candidates(
                workspace_id=uuid.uuid4(),
                query_text="ok",
                candidate_k=5,
            )
        sql_parts = [str(call.args[0]) for call in db.execute.call_args_list]
        main_sql = sql_parts[-1]
        self.assertIn("chunk_tsv_ru", main_sql)
        self.assertIn("chunk_tsv_simple", main_sql)
        self.assertIn("chunk_tsv_aux", main_sql)
        self.assertIn("@@", main_sql)
        self.assertNotIn("to_tsvector('russian', c.text)", main_sql)
        self.assertNotIn("to_tsvector('simple', c.text)", main_sql)

    def test_keyword_candidates_returns_empty_when_no_tsquery(self) -> None:
        db = MagicMock()
        repo = DocumentChunkRepository(db)
        with patch(
            "app.repositories.document_chunks.prepare_keyword_tsquery_texts",
            return_value=("", "", ""),
        ):
            out = repo.keyword_candidates(
                workspace_id=uuid.uuid4(),
                query_text="???",
                candidate_k=5,
            )
        self.assertEqual(out, [])
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
