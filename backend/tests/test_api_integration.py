import os
import uuid
import unittest

# Sync indexing for this flow (no Celery worker in integration job).
os.environ.setdefault("INGESTION_ASYNC_ENABLED", "0")

from fastapi.testclient import TestClient

from app.main import app


@unittest.skipUnless(
    __import__("os").environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class ApiFlowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_register_login_upload_search_delete_flow(self) -> None:
        email = f"it_{uuid.uuid4().hex[:10]}@example.com"
        password = "StrongPass123!"

        register_res = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Integration User"},
        )
        self.assertEqual(register_res.status_code, 200, register_res.text)
        user_payload = register_res.json()
        self.assertEqual(user_payload["email"], email)
        self.assertIn("id", user_payload)

        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login_res.status_code, 200, login_res.text)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        file_bytes = (
            b"Contract #A-2026\n"
            b"Price: 150000 KZT\n"
            b"Penalty: 0.1% per day of delay\n"
            b"Effective date: 2026-03-26\n"
        )
        upload_res = self.client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("contract.txt", file_bytes, "text/plain")},
        )
        self.assertEqual(upload_res.status_code, 200, upload_res.text)
        upload_payload = upload_res.json()
        self.assertGreater(upload_payload["chunks_created"], 0)
        document_id = upload_payload["document"]["id"]

        search_res = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "What is the price in KZT?", "top_k": 3},
        )
        self.assertEqual(search_res.status_code, 200, search_res.text)
        search_payload = search_res.json()
        self.assertGreaterEqual(len(search_payload["hits"]), 1)
        self.assertIn("150000", search_payload["answer"])
        self.assertIn(search_payload["decision"], ["answer", "clarify", "insufficient_context"])
        self.assertIsInstance(search_payload["confidence"], float)

        summary_res = self.client.get(f"/api/v1/documents/{document_id}/summary", headers=headers)
        self.assertEqual(summary_res.status_code, 200, summary_res.text)
        summary_payload = summary_res.json()
        self.assertEqual(summary_payload["document_id"], document_id)
        self.assertIn("150000", summary_payload["summary"])

        session_res = self.client.post("/api/v1/chat/sessions", headers=headers, json={"title": "Contract QA"})
        self.assertEqual(session_res.status_code, 200, session_res.text)
        session_id = session_res.json()["id"]

        chat_res = self.client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "Какая цена в договоре?", "top_k": 3},
        )
        self.assertEqual(chat_res.status_code, 200, chat_res.text)
        chat_payload = chat_res.json()
        self.assertEqual(chat_payload["session"]["id"], session_id)
        self.assertIn("150000", chat_payload["assistant_message"]["content"])
        self.assertGreaterEqual(len(chat_payload["assistant_message"]["sources"]), 1)
        self.assertIn(chat_payload["decision"], ["answer", "clarify", "insufficient_context"])
        self.assertIsInstance(chat_payload["confidence"], float)

        list_msgs_res = self.client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        self.assertEqual(list_msgs_res.status_code, 200, list_msgs_res.text)
        messages = list_msgs_res.json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

        delete_res = self.client.delete(f"/api/v1/documents/{document_id}", headers=headers)
        self.assertEqual(delete_res.status_code, 200, delete_res.text)
        self.assertTrue(delete_res.json()["ok"])


if __name__ == "__main__":
    unittest.main()
