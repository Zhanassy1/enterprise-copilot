import unittest

from app.core.security import generate_opaque_token, hash_opaque_token


class SecurityTokenTests(unittest.TestCase):
    def test_opaque_token_generation_has_entropy(self) -> None:
        a = generate_opaque_token()
        b = generate_opaque_token()
        self.assertNotEqual(a, b)
        self.assertGreater(len(a), 20)
        self.assertGreater(len(b), 20)

    def test_token_hash_is_deterministic(self) -> None:
        token = "abc123"
        self.assertEqual(hash_opaque_token(token), hash_opaque_token(token))
        self.assertNotEqual(hash_opaque_token(token), hash_opaque_token("abc124"))


if __name__ == "__main__":
    unittest.main()
