"""Regression: chunk retrieval SQL must filter by workspace_id (tenant isolation)."""

import unittest
import uuid

from app.services.vector_search import _dense_candidates, _keyword_candidates


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
        _dense_candidates(
            db,  # type: ignore[arg-type]
            workspace_id=wid,
            query_embedding=[0.1] * 384,
            candidate_k=10,
        )
        sql_text = str(captured["sql"])
        self.assertIn("workspace_id", sql_text.lower())
        self.assertEqual(captured["params"].get("workspace_id"), str(wid))

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
        _keyword_candidates(
            db,  # type: ignore[arg-type]
            workspace_id=wid,
            query_text="test",
            candidate_k=5,
        )
        self.assertIn("workspace_id", str(captured["sql"]).lower())
        self.assertEqual(captured["params"].get("workspace_id"), str(wid))


if __name__ == "__main__":
    unittest.main()
