"""
Cross-tenant isolation: object IDs from workspace B must not be readable when X-Workspace-Id is workspace A.
Requires PostgreSQL (same as test_api_integration). Run: RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_cross_workspace_access.py -v
"""

import os
import uuid
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.workspace_service import ensure_default_roles


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class CrossWorkspaceAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def _seed_two_workspaces(self) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
        """user_a, user_b, ws_a, ws_b, doc_b, chat_session_b."""
        db = SessionLocal()
        try:
            roles = ensure_default_roles(db)
            uid_a = uuid.uuid4()
            uid_b = uuid.uuid4()
            email_a = f"cross_a_{uid_a.hex[:8]}@example.com"
            email_b = f"cross_b_{uid_b.hex[:8]}@example.com"
            user_a = User(
                id=uid_a,
                email=email_a,
                password_hash=hash_password("CrossWsTest1!"),
                full_name="User A",
            )
            user_b = User(
                id=uid_b,
                email=email_b,
                password_hash=hash_password("CrossWsTest1!"),
                full_name="User B",
            )
            db.add(user_a)
            db.add(user_b)
            db.flush()

            ws_a = Workspace(
                id=uuid.uuid4(),
                name="Workspace A",
                owner_user_id=user_a.id,
                personal_for_user_id=user_a.id,
            )
            ws_b = Workspace(
                id=uuid.uuid4(),
                name="Workspace B",
                owner_user_id=user_b.id,
                personal_for_user_id=user_b.id,
            )
            db.add(ws_a)
            db.add(ws_b)
            db.flush()

            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws_a.id,
                    user_id=user_a.id,
                    role_id=roles["owner"].id,
                )
            )
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws_b.id,
                    user_id=user_b.id,
                    role_id=roles["owner"].id,
                )
            )
            db.flush()

            doc_b = Document(
                id=uuid.uuid4(),
                owner_id=user_b.id,
                workspace_id=ws_b.id,
                filename="secret.txt",
                content_type="text/plain",
                storage_key="/tmp/cross_workspace_placeholder_not_read",
                status="ready",
                file_size_bytes=10,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(doc_b)
            db.flush()

            sess_b = ChatSession(
                id=uuid.uuid4(),
                owner_id=user_b.id,
                workspace_id=ws_b.id,
                title="Secret chat",
            )
            db.add(sess_b)
            db.add(
                ChatMessage(
                    id=uuid.uuid4(),
                    session_id=sess_b.id,
                    role="user",
                    content="hello",
                    sources_json="[]",
                )
            )
            db.commit()
            return user_a.id, user_b.id, ws_a.id, ws_b.id, doc_b.id, sess_b.id
        finally:
            db.close()

    def test_user_cannot_delete_or_summarize_foreign_document(self) -> None:
        ua, _ub, ws_a, _ws_b, doc_b_id, _sess_b = self._seed_two_workspaces()

        db = SessionLocal()
        try:
            user_a = db.scalar(select(User).where(User.id == ua))
            assert user_a is not None
            email_a = user_a.email
        finally:
            db.close()

        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email_a, "password": "CrossWsTest1!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_a)}

        del_res = self.client.delete(f"/api/v1/documents/{doc_b_id}", headers=headers)
        self.assertEqual(del_res.status_code, 404, del_res.text)

        sum_res = self.client.get(f"/api/v1/documents/{doc_b_id}/summary", headers=headers)
        self.assertEqual(sum_res.status_code, 404, sum_res.text)

    def test_user_cannot_access_foreign_chat_session(self) -> None:
        ua, _ub, ws_a, _ws_b, _doc_b, sess_b_id = self._seed_two_workspaces()

        db = SessionLocal()
        try:
            user_a = db.scalar(select(User).where(User.id == ua))
            assert user_a is not None
            email_a = user_a.email
        finally:
            db.close()

        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email_a, "password": "CrossWsTest1!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_a)}

        list_res = self.client.get(f"/api/v1/chat/sessions/{sess_b_id}/messages", headers=headers)
        self.assertEqual(list_res.status_code, 404, list_res.text)

        msg_res = self.client.post(
            f"/api/v1/chat/sessions/{sess_b_id}/messages",
            headers=headers,
            json={"message": "ping", "top_k": 3},
        )
        self.assertEqual(msg_res.status_code, 404, msg_res.text)

    def test_billing_usage_requires_workspace_membership(self) -> None:
        ua, _ub, ws_a, ws_b, _doc_b, _sess_b = self._seed_two_workspaces()

        db = SessionLocal()
        try:
            user_a = db.scalar(select(User).where(User.id == ua))
            assert user_a is not None
            email_a = user_a.email
        finally:
            db.close()

        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email_a, "password": "CrossWsTest1!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_b)}
        res = self.client.get("/api/v1/billing/usage", headers=headers)
        self.assertEqual(res.status_code, 403, res.text)


if __name__ == "__main__":
    unittest.main()
