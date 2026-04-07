import unittest

from app.services.nlp import (
    PRICE_LINE_MARKERS,
    expand_query,
    is_contract_value_query,
    is_price_intent,
    is_strict_contract_value_query,
    text_has_contract_value_signal,
    text_has_monetary_amount,
)


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

    def test_contract_value_query_phrases(self) -> None:
        self.assertTrue(is_contract_value_query("стоимость договора"))
        self.assertTrue(is_contract_value_query("Какая сумма по договору?"))
        self.assertTrue(is_contract_value_query("цена контракта"))
        self.assertFalse(is_contract_value_query("сколько стоит лицензия"))
        self.assertFalse(is_contract_value_query("Срок поставки по договору"))

    def test_strict_contract_value_query_narrower_than_broad(self) -> None:
        self.assertTrue(is_strict_contract_value_query("стоимость договора"))
        self.assertTrue(is_strict_contract_value_query("сумма по договору?"))
        self.assertFalse(is_strict_contract_value_query("Условия оплаты по договору"))

    def test_contract_value_signal_russian_morphology(self) -> None:
        self.assertTrue(text_has_contract_value_signal("Цена договора составляет 12 000 000 тенге."))
        self.assertTrue(text_has_contract_value_signal("Стоимости договора определена в приложении."))
        self.assertTrue(text_has_contract_value_signal("Сумму по договору — 500 000 KZT."))
        self.assertTrue(text_has_contract_value_signal("Общая сумма по договору 1 000 000 тенге."))
        self.assertTrue(text_has_contract_value_signal("Условия по предметам договора и цена работ."))

    def test_contract_value_signal_false_for_security_sum_line(self) -> None:
        self.assertFalse(
            text_has_contract_value_signal(
                "внести сумму обеспечения исполнения Договора на равную 906 660.00 тенге"
            )
        )

    def test_expand_query_adds_price_keywords_once(self) -> None:
        q = "Какая сумма по договору?"
        expanded = expand_query(q)
        self.assertIn("сумма", expanded)
        self.assertIn("итого", expanded)
        self.assertIn("к оплате", expanded)
        self.assertIn("стоимость договора", expanded)
        self.assertTrue(expanded.startswith(q))

    def test_expand_query_unchanged_without_intent(self) -> None:
        plain = "Срок исполнения обязательств"
        self.assertEqual(expand_query(plain), plain)

    def test_clause_header_not_monetary_amount(self) -> None:
        self.assertFalse(text_has_monetary_amount("5.1. Оплата производится в течение 10 дней."))

    def test_spaced_sum_with_currency_is_monetary_amount(self) -> None:
        self.assertTrue(text_has_monetary_amount("1 500 000 тенге"))
        self.assertTrue(text_has_monetary_amount("Сумма 100 000 KZT"))

    def test_price_line_markers_utf8_cyrillic_and_currency(self) -> None:
        self.assertTrue(PRICE_LINE_MARKERS[0].startswith("цен"))
        self.assertIn("\u20b8", PRICE_LINE_MARKERS)
        self.assertIn("\u20bd", PRICE_LINE_MARKERS)
        self.assertIn("\u20ac", PRICE_LINE_MARKERS)
        blob = "".join(PRICE_LINE_MARKERS)
        self.assertNotIn("Ð", blob)
        self.assertNotIn("Р°", blob)


if __name__ == "__main__":
    unittest.main()
