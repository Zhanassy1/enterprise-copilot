import unittest

from app.services.nlp import expand_query, is_price_intent


class PriceIntentTests(unittest.TestCase):
    def test_sum_contract_queries_are_price_intent(self) -> None:
        self.assertTrue(is_price_intent("сумма договора"))
        self.assertTrue(is_price_intent("Какая сумма по договору?"))

    def test_total_and_payable_phrases_are_price_intent(self) -> None:
        self.assertTrue(is_price_intent("итого к оплате"))
        self.assertTrue(is_price_intent("к оплате по договору"))

    def test_non_price_queries_not_flagged(self) -> None:
        self.assertFalse(is_price_intent("итоги совещания за квартал"))
        self.assertFalse(is_price_intent("Срок поставки по договору"))

    def test_expand_query_adds_price_keywords_once(self) -> None:
        q = "Какая сумма по договору?"
        expanded = expand_query(q)
        self.assertIn("сумма", expanded)
        self.assertIn("итого", expanded)
        self.assertIn("к оплате", expanded)
        self.assertTrue(expanded.startswith(q))

    def test_expand_query_unchanged_without_intent(self) -> None:
        plain = "Срок исполнения обязательств"
        self.assertEqual(expand_query(plain), plain)


if __name__ == "__main__":
    unittest.main()
