import unittest

from app.services.nlp import filter_ungrounded_sentences


class GroundingFilterTests(unittest.TestCase):
    def test_removes_unsupported_sentence(self) -> None:
        hits = [
            {"text": "Цена договора составляет 150000 KZT. Срок оплаты 10 дней.", "score": 0.9},
        ]
        answer = (
            "Цена договора 150000 KZT. "
            "Компания обязана поставить товар в течение 2 дней после аванса."
        )
        filtered = filter_ungrounded_sentences(answer, "Какая цена договора?", hits)
        self.assertIn("150000", filtered)
        self.assertNotIn("2 дней", filtered)

    def test_returns_fallback_when_nothing_grounded(self) -> None:
        hits = [{"text": "Общие положения и подписи сторон.", "score": 0.3}]
        answer = "Сумма штрафа 10% за каждый день просрочки."
        filtered = filter_ungrounded_sentences(answer, "Какой штраф?", hits)
        self.assertIn("Недостаточно данных", filtered)


if __name__ == "__main__":
    unittest.main()
