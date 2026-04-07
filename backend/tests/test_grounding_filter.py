import unittest

from app.services.nlp import compress_price_answer, filter_ungrounded_sentences


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

    def test_spaced_thousands_amount_stays_grounded(self) -> None:
        hits = [{"text": "Итого: 1 500 000 тенге за услуги.", "score": 0.9}]
        answer = "По договору сумма составляет 1 500 000 тенге."
        filtered = filter_ungrounded_sentences(answer, "Какая сумма по договору?", hits)
        self.assertIn("1 500 000", filtered)
        self.assertNotIn("Недостаточно данных", filtered)

    def test_price_query_drops_numbered_security_obligations(self) -> None:
        hits = [
            {
                "text": "1) Обеспечить исполнение. 2) Внести сумму обеспечения 906 660.00 тенге.",
                "score": 0.9,
            }
        ]
        answer = "1) внести сумму обеспечения 906 660.00 тенге"
        filtered = filter_ungrounded_sentences(answer, "стоимость договора", hits)
        self.assertIn("Недостаточно данных", filtered)

    def test_compress_price_answer_prefers_contract_line_from_hits(self) -> None:
        hits = [
            {"text": "Обеспечение 100 тенге.", "score": 0.5},
            {"text": "Цена договора 12 132 132 тенге.", "score": 0.9},
        ]
        noisy = (
            "1) Первый пункт.\n"
            "2) Второй пункт с 100 тенге.\n"
            "Лишний текст."
        )
        out = compress_price_answer("стоимость договора", noisy, hits)
        self.assertIn("12 132 132", out)
        self.assertNotIn("1)", out)


if __name__ == "__main__":
    unittest.main()
