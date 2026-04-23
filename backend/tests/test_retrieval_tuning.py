"""Unit tests for query-kind inference (no DB)."""

from __future__ import annotations

import unittest

from app.services.retrieval.tuning import infer_query_kind


class RetrievalTuningTests(unittest.TestCase):
    def test_code_like_sku(self) -> None:
        self.assertEqual(infer_query_kind("MIL-SPEC-99X"), "code_like")

    def test_default_arbitrary(self) -> None:
        self.assertEqual(infer_query_kind("общие условия поставки оборудования"), "default")


if __name__ == "__main__":
    unittest.main()
