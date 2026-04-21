"""Unit tests for chunk_search_aux and keyword query heuristics."""

from __future__ import annotations

import unittest

from app.services.retrieval.chunk_search_aux import build_chunk_search_aux
from app.services.retrieval.keyword_query import is_code_like_keyword_query


class ChunkSearchAuxTests(unittest.TestCase):
    def test_extracts_sku_and_gost_tokens(self) -> None:
        text = "артикул MIL-SPEC-99X/12.3 и ГОСТ 12345-89. Приложение № 4."
        aux = build_chunk_search_aux(text)
        self.assertIn("MIL-SPEC-99X/12.3", aux)
        self.assertIn("12345-89", aux)
        self.assertIn("Приложение № 4", aux)

    def test_empty_input(self) -> None:
        self.assertEqual(build_chunk_search_aux(""), "")


class CodeLikeQueryTests(unittest.TestCase):
    def test_single_token_sku(self) -> None:
        self.assertTrue(is_code_like_keyword_query("MIL-SPEC-99X"))

    def test_rejects_plain_word(self) -> None:
        self.assertFalse(is_code_like_keyword_query("test"))

    def test_rejects_spaced_prose(self) -> None:
        self.assertFalse(is_code_like_keyword_query("цена договора"))

    def test_rejects_empty(self) -> None:
        self.assertFalse(is_code_like_keyword_query(""))


if __name__ == "__main__":
    unittest.main()
