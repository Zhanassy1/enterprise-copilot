"""
Upload metering outbox → usage_events (PostgreSQL, idempotent projection).

Run: RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_usage_outbox_integration.py -v
"""

from __future__ import annotations

import json
import os
import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.billing import UsageEvent, UsageOutbox
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.usage_metering import EVENT_DOCUMENT_UPLOAD, EVENT_UPLOAD_BYTES
from app.services.usage_outbox import (
    OUTBOX_PENDING,
    OUTBOX_SENT,
    process_usage_outbox_batch,
    upload_metering_idempotency_key,
)
from app.services.workspace_service import ensure_default_roles


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION_TESTS") == "1",
    "Set RUN_INTEGRATION_TESTS=1 to run integration tests.",
)
class UsageOutboxIntegrationTests(unittest.TestCase):
    def test_outbox_projects_idempotently(self) -> None:
        db = SessionLocal()
        try:
            roles = ensure_default_roles(db)
            uid = uuid.uuid4()
            user = User(
                id=uid,
                email=f"outbox_{uid.hex[:10]}@example.com",
                password_hash=hash_password("OutboxTest1!"),
                full_name="Outbox Test",
            )
            db.add(user)
            db.flush()
            ws = Workspace(
                id=uuid.uuid4(),
                name="Outbox WS",
                slug=f"outbox-ws-{uuid.uuid4().hex[:10]}",
                owner_user_id=user.id,
                personal_for_user_id=user.id,
            )
            db.add(ws)
            db.flush()
            db.add(
                WorkspaceMember(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    user_id=user.id,
                    role_id=roles["owner"].id,
                )
            )
            doc = Document(
                id=uuid.uuid4(),
                owner_id=user.id,
                workspace_id=ws.id,
                filename="meter.txt",
                content_type="text/plain",
                storage_key=f"/tmp/outbox_{uuid.uuid4().hex}",
                status="queued",
                file_size_bytes=42,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(doc)
            db.flush()
            k1 = upload_metering_idempotency_key(doc.id, "document_upload")
            k2 = upload_metering_idempotency_key(doc.id, "document_upload_bytes")
            db.add(
                UsageOutbox(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    document_id=doc.id,
                    user_id=user.id,
                    event_type=EVENT_DOCUMENT_UPLOAD,
                    quantity=1,
                    unit="count",
                    metadata_json=json.dumps({"document_id": str(doc.id), "filename": doc.filename}),
                    idempotency_key=k1,
                    status=OUTBOX_PENDING,
                )
            )
            db.add(
                UsageOutbox(
                    id=uuid.uuid4(),
                    workspace_id=ws.id,
                    document_id=doc.id,
                    user_id=user.id,
                    event_type=EVENT_UPLOAD_BYTES,
                    quantity=42,
                    unit="bytes",
                    metadata_json=json.dumps({"document_id": str(doc.id)}),
                    idempotency_key=k2,
                    status=OUTBOX_PENDING,
                )
            )
            db.commit()

            r1 = process_usage_outbox_batch(db, limit=10)
            self.assertEqual(r1["processed"], 2)
            r2 = process_usage_outbox_batch(db, limit=10)
            self.assertEqual(r2["processed"], 0)

            n_usage = db.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(UsageEvent.workspace_id == ws.id, UsageEvent.idempotency_key.in_((k1, k2)))
            )
            self.assertEqual(int(n_usage or 0), 2)

            n_sent = db.scalar(
                select(func.count()).select_from(UsageOutbox).where(UsageOutbox.document_id == doc.id, UsageOutbox.status == OUTBOX_SENT)
            )
            self.assertEqual(int(n_sent or 0), 2)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
