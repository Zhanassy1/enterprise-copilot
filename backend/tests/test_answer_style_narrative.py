import unittest

from app.services.nlp import (
    compress_price_answer,
    is_advisory_intent,
    postprocess_llm_answer,
    resolve_answer_style,
)


class AnswerStyleTests(unittest.TestCase):
    def test_resolve_answer_style(self) -> None:
        self.assertEqual(resolve_answer_style(None, "concise"), "concise")
        self.assertEqual(resolve_answer_style("narrative", "concise"), "narrative")

    def test_is_advisory_intent(self) -> None:
        self.assertTrue(is_advisory_intent("какие риски в этом договоре"))
        self.assertTrue(is_advisory_intent("нормальная ли сумма"))
        self.assertFalse(is_advisory_intent("какая стоимость договора"))

    def test_compress_narrative_keeps_short_paragraph_with_amount(self) -> None:
        hits = [
            {
                "text": "Цена договора составляет 99 999 тенге за услуги по приложению 1.",
                "score": 0.9,
            },
        ]
        llm = (
            "Цена договора — 99 999 тенге. Сумма указана за услуги по приложению 1. "
            "Других сумм в фрагменте нет."
        )
        out = compress_price_answer(
            "стоимость договора",
            llm,
            hits,
            answer_style="narrative",
        )
        self.assertIn("99 999", out)
        self.assertIn("приложен", out.lower())

    def test_postprocess_keeps_advisory_disclaimer(self) -> None:
        hits = [{"text": "Штраф 10% за просрочку. Срок 5 дней.", "score": 0.9}]
        raw = (
            "По документам: предусмотрен штраф 10% за просрочку, срок оплаты 5 дней.\n\n"
            "Возможные точки внимания: при длительной просрочке сумма штрафа может нарастать.\n\n"
            "Ответ носит информационный характер и не является юридической консультацией."
        )
        out = postprocess_llm_answer(
            "есть ли риски по штрафам",
            raw,
            hits,
            answer_style="narrative",
        )
        self.assertIn("10%", out)
        self.assertIn("юридическ", out.lower())
        self.assertIn("информацион", out.lower())


if __name__ == "__main__":
    unittest.main()
