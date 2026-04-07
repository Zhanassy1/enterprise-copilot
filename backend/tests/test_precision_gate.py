import unittest

from pydantic import ValidationError

from app.core.settings.llm import LLMSettings
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

    def test_clarify_band_with_default_style_thresholds(self) -> None:
        hits = [
            {"text": "Оплата в течение 10 дней после акта по этапам", "score": 0.74},
            {"text": "Стоимость и спецификация", "score": 0.30},
        ]
        decision, confidence = decide_response_mode(
            "Условия оплаты по этапам",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertEqual(decision, "clarify")
        self.assertGreaterEqual(confidence, 0.48)
        self.assertLess(confidence, 0.55)

    def test_answer_mode_when_confidence_at_or_above_default_answer_threshold(self) -> None:
        hits = [
            {"text": "Оплата в течение 10 дней после акта по этапам", "score": 0.82},
            {"text": "Стоимость и спецификация", "score": 0.30},
        ]
        decision, confidence = decide_response_mode(
            "Условия оплаты по этапам",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertEqual(decision, "answer")
        self.assertGreaterEqual(confidence, 0.55)

    def test_answer_mode_price_intent_when_amount_in_second_hit_not_first(self) -> None:
        """Reranker noise in rank-1 must not drop into clarify if a later hit has price + amount."""
        hits = [
            {"text": "тенге тенге", "score": 1.0},
            {"text": "Цена договора составляет 906 660.00 тенге.", "score": 0.99},
        ]
        decision, confidence = decide_response_mode(
            "Какая стоимость договора?",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertEqual(decision, "answer")
        self.assertGreaterEqual(confidence, 0.55)

    def test_answer_mode_inflected_contract_price_in_second_hit(self) -> None:
        """Morphological «цена договора» (not substring «цена договор») still triggers evidence + confidence."""
        hits = [
            {"text": "тенге договору", "score": 1.0},
            {
                "text": "Стоимость договора определена как 15 000 000 тенге (пятнадцать миллионов).",
                "score": 0.4,
            },
        ]
        decision, _conf = decide_response_mode(
            "стоимость договора",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertEqual(decision, "answer")

    def test_no_force_answer_when_only_security_deposit_line(self) -> None:
        hits = [
            {
                "text": "внести сумму обеспечения исполнения Договора на равную 906 660.00 тенге.",
                "score": 0.85,
            },
        ]
        decision, confidence = decide_response_mode(
            "стоимость договора",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertNotEqual(decision, "answer")
        self.assertLess(confidence, 0.55)

    def test_answer_mode_termination_intent_when_marker_in_second_hit(self) -> None:
        hits = [
            {"text": "Общие условия поставки товара.", "score": 1.0},
            {
                "text": "Договор может быть расторгнут по соглашению сторон либо в судебном порядке.",
                "score": 0.99,
            },
        ]
        decision, confidence = decide_response_mode(
            "Условия расторжения договора",
            hits,
            answer_threshold=0.55,
            clarify_threshold=0.48,
        )
        self.assertEqual(decision, "answer")
        self.assertGreaterEqual(confidence, 0.55)

    def test_llm_settings_rejects_clarify_not_strictly_below_answer(self) -> None:
        with self.assertRaises(ValidationError):
            LLMSettings(answer_threshold=0.55, clarify_threshold=0.55)


if __name__ == "__main__":
    unittest.main()
