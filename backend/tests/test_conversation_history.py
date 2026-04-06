"""Tests for RAG conversation history formatting."""

import unittest
from types import SimpleNamespace

from app.services.conversation_history import format_prior_messages_for_rag


class ConversationHistoryTests(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(format_prior_messages_for_rag([]))

    def test_formats_user_and_assistant(self) -> None:
        msgs = [
            SimpleNamespace(role="user", content="Про цену?"),
            SimpleNamespace(role="assistant", content="150000 KZT по договору."),
        ]
        out = format_prior_messages_for_rag(msgs)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("Пользователь:", out)
        self.assertIn("Про цену?", out)
        self.assertIn("Ассистент:", out)
        self.assertIn("150000", out)

    def test_truncates_long_assistant(self) -> None:
        long_body = "x" * 5000
        msgs = [SimpleNamespace(role="assistant", content=long_body)]
        out = format_prior_messages_for_rag(msgs)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertLess(len(out), len(long_body))
        self.assertTrue(out.endswith("…") or len(out) < len(long_body))


if __name__ == "__main__":
    unittest.main()
