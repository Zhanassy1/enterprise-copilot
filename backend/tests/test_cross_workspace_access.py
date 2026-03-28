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
from app.models.document import Document, IngestionJob
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

            job_b = IngestionJob(
                id=uuid.uuid4(),
                document_id=doc_b.id,
                workspace_id=ws_b.id,
                status="failed",
                attempts=1,
                deduplication_key=f"{ws_b.id}:{doc_b.id}",
                celery_task_id=str(uuid.uuid4()),
                error_message="seed",
            )
            db.add(job_b)
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

    def _seed_owner_and_viewer(self) -> tuple[uuid.UUID, uuid.UUID, str]:
        """owner user, workspace, viewer user email (viewer-only role in that workspace)."""
        db = SessionLocal()
        try:
            roles = ensure_default_roles(db)
            uid_owner = uuid.uuid4()
            uid_viewer = uuid.uuid4()
            email_o = f"owner_{uid_owner.hex[:8]}@example.com"
            email_v = f"viewer_{uid_viewer.hex[:8]}@example.com"
            owner = User(
                id=uid_owner,
                email=email_o,
                password_hash=hash_password("CrossWsTest1!"),
                full_name="Owner",
            )
            viewer = User(
                id=uid_viewer,
                email=email_v,
                password_hash=hash_password("CrossWsTest1!"),
                full_name="Viewer",
            )
            db.add(owner)
            db.add(viewer)
            db.flush()
            ws = Workspace(
                id=uuid.uuid4(),
                name="WS owner+viewer",
                owner_user_id=owner.id,
                personal_for_user_id=owner.id,
            )
            db.add(ws)
            db.flush()
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    user_id=owner.id,
                    role_id=roles["owner"].id,
                )
            )
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    user_id=viewer.id,
                    role_id=roles["viewer"].id,
                )
            )
            db.commit()
            return ws.id, viewer.id, email_v
        finally:
            db.close()

    def test_viewer_can_list_documents_but_cannot_upload(self) -> None:
        ws_id, _vid, email_v = self._seed_owner_and_viewer()
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email_v, "password": "CrossWsTest1!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_id)}
        list_res = self.client.get("/api/v1/documents", headers=headers)
        self.assertEqual(list_res.status_code, 200, list_res.text)
        up_res = self.client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("note.txt", b"hello world", "text/plain")},
        )
        self.assertEqual(up_res.status_code, 403, up_res.text)
        detail = str(up_res.json().get("detail") or "").lower()
        self.assertTrue("role" in detail or "insufficient" in detail, msg=up_res.text)

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

    def test_user_cannot_use_foreign_workspace_header(self) -> None:
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

    def test_search_and_billing_scoped_to_workspace(self) -> None:
        ua, _ub, ws_a, _ws_b, _doc_b, _sess_b = self._seed_two_workspaces()
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
        search_res = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "contract penalty", "top_k": 3},
        )
        self.assertEqual(search_res.status_code, 200, search_res.text)
        bill_res = self.client.get("/api/v1/billing/usage", headers=headers)
        self.assertEqual(bill_res.status_code, 200, bill_res.text)
        self.assertIn("plan_slug", bill_res.json())

    def test_user_cannot_get_or_download_foreign_document(self) -> None:
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
        get_res = self.client.get(f"/api/v1/documents/{doc_b_id}", headers=headers)
        self.assertEqual(get_res.status_code, 404, get_res.text)
        dl_res = self.client.get(f"/api/v1/documents/{doc_b_id}/download", headers=headers, follow_redirects=False)
        self.assertEqual(dl_res.status_code, 404, dl_res.text)

    def test_user_cannot_read_foreign_document_ingestion(self) -> None:
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
        ing_res = self.client.get(f"/api/v1/documents/{doc_b_id}/ingestion", headers=headers)
        self.assertEqual(ing_res.status_code, 404, ing_res.text)

    def test_chat_sessions_list_only_current_workspace(self) -> None:
        ua, _ub, ws_a, _ws_b, _doc_b, sess_b = self._seed_two_workspaces()
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
        res = self.client.get("/api/v1/chat/sessions", headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        ids = {x["id"] for x in res.json()}
        self.assertNotIn(str(sess_b), ids)

    def test_ingestion_jobs_list_scoped_no_foreign_job_ids(self) -> None:
        ua, _ub, ws_a, ws_b, _doc_b, _sess_b = self._seed_two_workspaces()
        db = SessionLocal()
        try:
            user_a = db.scalar(select(User).where(User.id == ua))
            assert user_a is not None
            email_a = user_a.email
            jobs_b = db.scalars(
                select(IngestionJob).where(IngestionJob.workspace_id == ws_b)
            ).all()
            job_ids_b = {str(j.id) for j in jobs_b}
        finally:
            db.close()
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email_a, "password": "CrossWsTest1!"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws_a)}
        res = self.client.get("/api/v1/ingestion/jobs", headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        for row in res.json():
            self.assertNotIn(row["id"], job_ids_b)
            self.assertEqual(row["workspace_id"], str(ws_a))


if __name__ == "__main__":
    unittest.main()
