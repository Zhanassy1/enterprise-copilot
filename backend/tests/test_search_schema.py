import unittest

from pydantic import ValidationError

from app.schemas.documents import SearchIn


class SearchInSchemaTests(unittest.TestCase):
    def test_query_is_trimmed(self) -> None:
        payload = SearchIn(query="   contract price   ", top_k=5)
        self.assertEqual(payload.query, "contract price")

    def test_empty_query_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SearchIn(query="   ", top_k=5)

    def test_top_k_above_limit_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SearchIn(query="price", top_k=100)

    def test_top_k_lower_bound_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SearchIn(query="price", top_k=0)


if __name__ == "__main__":
    unittest.main()
