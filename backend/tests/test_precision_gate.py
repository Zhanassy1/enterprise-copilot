import unittest

from app.services.nlp import decide_response_mode


class PrecisionGateTests(unittest.TestCase):
    def test_answer_mode_for_high_confidence_hit(self) -> None:
        hits = [
            {"text": "Цена договора 150000 KZT. Оплата 10 дней.", "score": 0.92},
            {"text": "Общие положения договора.", "score": 0.40},
        ]
        decision, confidence = decide_response_mode(
            "Какая цена в KZT?",
            hits,
            answer_threshold=0.62,
            clarify_threshold=0.42,
        )
        self.assertEqual(decision, "answer")
        self.assertGreaterEqual(confidence, 0.62)

    def test_clarify_mode_for_mid_confidence_hit(self) -> None:
        hits = [
            {"text": "В договоре указаны условия оплаты и срок оплаты 10 дней.", "score": 0.60},
            {"text": "Приложение с реквизитами сторон.", "score": 0.54},
        ]
        decision, confidence = decide_response_mode(
            "Условия оплаты по договору",
            hits,
            answer_threshold=0.80,
            clarify_threshold=0.40,
        )
        self.assertEqual(decision, "clarify")
        self.assertGreaterEqual(confidence, 0.40)
        self.assertLess(confidence, 0.80)

    def test_insufficient_context_mode_when_no_hits(self) -> None:
        decision, confidence = decide_response_mode(
            "Какой штраф за просрочку?",
            [],
            answer_threshold=0.62,
            clarify_threshold=0.42,
        )
        self.assertEqual(decision, "insufficient_context")
        self.assertEqual(confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
