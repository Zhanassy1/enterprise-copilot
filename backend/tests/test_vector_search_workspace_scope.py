"""Regression: chunk retrieval SQL must filter by workspace_id (tenant isolation)."""

import unittest
import uuid
from unittest.mock import patch

from app.services.retrieval.generic_hybrid import dense_candidates, keyword_candidates


class VectorSearchWorkspaceScopeTests(unittest.TestCase):
    def test_dense_sql_binds_workspace_id(self) -> None:
        captured: dict = {}

        class _Exec:
            def execute(self, sql, params):
                captured["sql"] = sql
                captured["params"] = dict(params)
                class R:
                    def mappings(self):
                        return iter([])

                return R()

        db = _Exec()
        wid = uuid.uuid4()
        dim = 256
        with patch("app.repositories.document_chunks.get_embedding_dim", return_value=dim):
            dense_candidates(
                db,  # type: ignore[arg-type]
                workspace_id=wid,
                query_embedding=[0.1] * dim,
                candidate_k=10,
            )
        sql_text = str(captured["sql"])
        self.assertIn("workspace_id", sql_text.lower())
        self.assertEqual(captured["params"].get("workspace_id"), str(wid))
        self.assertIn(f"vector({dim})", sql_text)

    def test_keyword_sql_binds_workspace_id(self) -> None:
        captured: dict = {}

        class _Exec:
            def execute(self, sql, params):
                captured["sql"] = sql
                captured["params"] = dict(params)
                class R:
                    def mappings(self):
                        return iter([])

                return R()

        db = _Exec()
        wid = uuid.uuid4()
        keyword_candidates(
            db,  # type: ignore[arg-type]
            workspace_id=wid,
            query_text="test",
            candidate_k=5,
        )
        self.assertIn("workspace_id", str(captured["sql"]).lower())
        self.assertEqual(captured["params"].get("workspace_id"), str(wid))


if __name__ == "__main__":
    unittest.main()
