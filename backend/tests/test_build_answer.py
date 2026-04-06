"""Unit tests for ``build_answer`` (extractive vs LLM path)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.nlp import build_answer


class BuildAnswerTests(unittest.TestCase):
    @patch("app.services.llm.llm_enabled", return_value=False)
    def test_no_hits_returns_not_found_message(self, _mock_llm: object) -> None:
        out = build_answer("вопрос", [])
        self.assertIn("не найдено", out.lower())

    @patch("app.services.llm.llm_enabled", return_value=False)
    def test_extractive_when_llm_disabled(self, _mock_llm: object) -> None:
        hits = [{"text": "Стоимость услуги 999 KZT за единицу.", "score": 0.9}]
        out = build_answer("стоимость KZT", hits)
        self.assertIn("999", out)

    @patch("app.services.llm.rag_answer", return_value="Стоимость 42 KZT по тарифу.")
    @patch("app.services.llm.llm_enabled", return_value=True)
    def test_llm_path_when_enabled_and_grounded(self, _mock_enabled: object, _mock_rag: object) -> None:
        hits = [{"text": "Тариф: стоимость 42 KZT за услугу.", "score": 0.95}]
        out = build_answer("стоимость KZT", hits)
        self.assertIn("42", out)

    @patch("app.services.llm.rag_answer", return_value="")
    @patch("app.services.llm.llm_enabled", return_value=True)
    def test_falls_back_to_extractive_when_llm_returns_empty(
        self,
        _mock_enabled: object,
        _mock_rag: object,
    ) -> None:
        hits = [{"text": "Пеня 1% за день просрочки.", "score": 0.88}]
        out = build_answer("пеня", hits)
        self.assertIn("1%", out)


if __name__ == "__main__":
    unittest.main()
