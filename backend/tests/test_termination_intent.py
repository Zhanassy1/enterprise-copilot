"""Termination / contract-end query intent (mirrors penalty intent tests)."""

import unittest

from app.services.nlp import (
    TERMINATION_LINE_MARKERS,
    expand_query,
    is_termination_intent,
)


class TerminationIntentTests(unittest.TestCase):
    def test_termination_phrases_detected(self) -> None:
        self.assertTrue(is_termination_intent("Условия расторжения договора"))
        self.assertTrue(is_termination_intent("Как расторгнуть договор?"))
        self.assertTrue(is_termination_intent("односторонний отказ"))
        self.assertTrue(is_termination_intent("уведомление о расторжении"))
        self.assertTrue(is_termination_intent("отказ от договора"))
        self.assertTrue(is_termination_intent("прекращение действия договора"))

    def test_unrelated_queries_not_flagged(self) -> None:
        self.assertFalse(is_termination_intent("Какая сумма по договору?"))
        self.assertFalse(is_termination_intent("Срок поставки"))

    def test_expand_query_adds_termination_keywords(self) -> None:
        q = "Условия расторжения?"
        expanded = expand_query(q)
        self.assertIn("расторжение", expanded)
        self.assertTrue(expanded.startswith(q))

    def test_termination_markers_are_substrings(self) -> None:
        self.assertIn("расторж", TERMINATION_LINE_MARKERS)


if __name__ == "__main__":
    unittest.main()
