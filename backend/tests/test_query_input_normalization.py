"""Unit tests for search query normalization before retrieval / tsquery."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.services.retrieval.keyword_query import is_code_like_keyword_query
from app.services.retrieval.query_input import normalize_search_query_for_retrieval


class NormalizeSearchQueryTests(unittest.TestCase):
    def test_idempotent(self) -> None:
        a = "  price \n contract  "
        b = normalize_search_query_for_retrieval(a)
        c = normalize_search_query_for_retrieval(b)
        self.assertEqual(b, c)
        self.assertEqual(b, "price contract")

    def test_nfc(self) -> None:
        s = "caf\u00e9"
        t = "caf\u0065\u0301"
        self.assertNotEqual(s, t)
        self.assertEqual(normalize_search_query_for_retrieval(s), normalize_search_query_for_retrieval(t))

    def test_null_and_zwsp(self) -> None:
        self.assertEqual(
            normalize_search_query_for_retrieval("a\x00b\u200b c"),
            "ab c",
        )
        # only ZWSP / BOM between letters (strip does not remove U+200B in Python)
        raw = "x\u200b\u200c\u200d\ufeffy"
        self.assertEqual(normalize_search_query_for_retrieval(raw), "xy")

    def test_mixed_newlines(self) -> None:
        self.assertEqual(
            normalize_search_query_for_retrieval("one\r\ntwo\tthree"),
            "one two three",
        )

    def test_cyrillic_unchanged_semantics(self) -> None:
        s = "  цена  договора  "
        self.assertEqual(normalize_search_query_for_retrieval(s), "цена договора")

    def test_code_like_sku_unchanged_for_heuristic(self) -> None:
        for sku in ("MIL-SPEC-99X", "SKU-12/34", "GOST-12345-89"):
            n = normalize_search_query_for_retrieval(f"  {sku}  ")
            self.assertTrue(
                is_code_like_keyword_query(n),
                f"expected code-like after normalize: {sku!r} -> {n!r}",
            )

    def test_strips_c1(self) -> None:
        t = f"a{chr(0x9d)}b"  # U+009D
        n = normalize_search_query_for_retrieval(t)
        self.assertNotIn(chr(0x9D), n)
        self.assertIn("a", n)
        self.assertIn("b", n)

    def test_fallback_not_worse_than_strip_only(self) -> None:
        s = "  text  "
        self.assertTrue(normalize_search_query_for_retrieval(s))


class KeywordQueryUsesNormalizedQTests(unittest.TestCase):
    def test_prepare_keyword_gets_clean_q_after_normalize(self) -> None:
        """
        Callers (via vector_search → prepare_keyword) should pass
        ``normalize_search_query_for_retrieval`` output so :q has no NUL/ZWSP.
        """
        from app.services.retrieval import keyword_query as kq

        captured: list[dict] = []

        def execute_side(*args, **kwargs) -> MagicMock:
            p = args[1] if len(args) > 1 else None
            if isinstance(p, dict) and p.get("q") is not None:
                captured.append(p.copy())
            m = MagicMock()
            m.scalar.return_value = ""
            return m

        db = MagicMock()
        db.execute = MagicMock(side_effect=execute_side)
        n = normalize_search_query_for_retrieval("  foo \x00 bar  ")
        kq.prepare_keyword_tsquery_texts(db, n)
        self.assertNotIn(
            "\x00",
            "".join(p.get("q", "") for p in captured),
        )
        self.assertTrue(
            any(p.get("q") == "foo bar" for p in captured),
            f"expected :q 'foo bar', got {captured!r}",
        )


if __name__ == "__main__":
    unittest.main()
