"""Ranking heuristics for contract-value vs security-deposit chunks."""

from __future__ import annotations

import unittest

from app.services.vector_search import _apply_quality_heuristics


class VectorSearchContractValueTests(unittest.TestCase):
    def test_contract_value_query_puts_contract_price_chunk_first(self) -> None:
        rows = [
            {
                "chunk_id": "sec",
                "text": "1) Обеспечить исполнение. 2) Сумма обеспечения 906 660 тенге.",
                "score": 0.5,
            },
            {
                "chunk_id": "price",
                "text": "Цена договора составляет 12 000 000 тенге (двенадцать миллионов).",
                "score": 0.5,
            },
        ]
        out = _apply_quality_heuristics("стоимость договора", rows)
        self.assertEqual(out[0]["chunk_id"], "price")
        self.assertEqual(out[1]["chunk_id"], "sec")


if __name__ == "__main__":
    unittest.main()
