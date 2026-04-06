"""Penalty / sanctions query intent and expand_query (mirrors price intent tests)."""

from __future__ import annotations

import unittest

from app.services.nlp import expand_query, is_penalty_intent


class PenaltyIntentTests(unittest.TestCase):
    def test_sanctions_and_withholding_queries_are_penalty_intent(self) -> None:
        self.assertTrue(is_penalty_intent("санкции по договору"))
        self.assertTrue(is_penalty_intent("удержание с оплаты"))

    def test_existing_penalty_keywords_still_match(self) -> None:
        self.assertTrue(is_penalty_intent("Какая неустойка за просрочку?"))
        self.assertTrue(is_penalty_intent("штраф за нарушение срока"))

    def test_non_penalty_queries_not_flagged(self) -> None:
        self.assertFalse(is_penalty_intent("Срок поставки по договору"))
        self.assertFalse(is_penalty_intent("Какая сумма по договору?"))

    def test_expand_query_adds_penalty_keywords_once(self) -> None:
        q = "санкции за нарушение условий"
        expanded = expand_query(q)
        self.assertIn("санкции", expanded)
        self.assertIn("удержание", expanded)
        self.assertTrue(expanded.startswith(q))

    def test_expand_query_unchanged_without_intent(self) -> None:
        plain = "Срок исполнения обязательств"
        self.assertEqual(expand_query(plain), plain)


if __name__ == "__main__":
    unittest.main()
