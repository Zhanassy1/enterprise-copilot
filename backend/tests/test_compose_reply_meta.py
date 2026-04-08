import unittest

from app.services.nlp import (
    compose_response_text,
    filter_ungrounded_sentences,
    parse_reply_meta,
    serialize_reply_meta,
)


class ComposeResponseTests(unittest.TestCase):
    def test_answer_returns_body_only(self) -> None:
        text = compose_response_text(
            decision="answer",
            answer="  Цена 100 KZT.  ",
            details="meta",
            clarifying_question=None,
            next_step="шаг",
        )
        self.assertEqual(text, "Цена 100 KZT.")

    def test_clarify_includes_question_and_next_step(self) -> None:
        text = compose_response_text(
            decision="clarify",
            answer="ignored",
            details=None,
            clarifying_question="Какой документ?",
            next_step="Добавьте период",
        )
        self.assertIn("Нужна конкретизация", text)
        self.assertIn("Какой документ?", text)
        self.assertIn("Следующий шаг", text)
        self.assertIn("Добавьте период", text)

    def test_insufficient_context_includes_clarify_and_next_step(self) -> None:
        text = compose_response_text(
            decision="insufficient_context",
            answer="",
            details=None,
            clarifying_question="Уточните запрос",
            next_step="Загрузите документ",
        )
        self.assertIn("Недостаточно подтвержденных", text)
        self.assertIn("Уточните запрос", text)
        self.assertIn("Загрузите документ", text)

    def test_serialize_parse_roundtrip(self) -> None:
        raw = serialize_reply_meta(
            decision="answer",
            details="d",
            next_step="n",
            clarifying_question=None,
        )
        self.assertIsNotNone(raw)
        d, n, cq, dec, st = parse_reply_meta(raw)
        self.assertEqual(d, "d")
        self.assertEqual(n, "n")
        self.assertIsNone(cq)
        self.assertEqual(dec, "answer")
        self.assertIsNone(st)

    def test_serialize_includes_answer_style(self) -> None:
        raw = serialize_reply_meta(
            decision="answer",
            details="d",
            next_step="n",
            clarifying_question=None,
            answer_style="narrative",
        )
        self.assertIsNotNone(raw)
        _d, _n, _cq, dec, st = parse_reply_meta(raw)
        self.assertEqual(dec, "answer")
        self.assertEqual(st, "narrative")


class ListGroundingTests(unittest.TestCase):
    def test_keeps_bullet_lines_with_support(self) -> None:
        hits = [
            {
                "text": "Пеня 0.1% за день просрочки. Срок оплаты 10 дней.",
                "score": 0.9,
            },
        ]
        answer = "По документу:\n- Пеня 0.1% за день\n- Срок оплаты 10 дней"
        filtered = filter_ungrounded_sentences(answer, "пеня", hits)
        self.assertIn("0.1%", filtered)
        self.assertIn("- Пеня", filtered)
        self.assertIn("- Срок оплаты", filtered)


if __name__ == "__main__":
    unittest.main()
