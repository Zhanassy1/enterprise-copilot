"""
Seed a minimal workspace + document + chunks for offline retrieval eval (integration tests / local eval).

Uses fixed chunk UUIDs matching ``eval/retrieval_gold.jsonl``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.document_chunks import DocumentChunkRepository
from app.services.embeddings import embed_texts, get_embedding_dim
from app.services.usage_metering import get_or_create_quota
from app.services.workspace_service import ensure_default_roles

# Must match backend/eval/retrieval_gold.jsonl
CHUNK_ID_PRICE = uuid.UUID("f0000001-0001-0001-0001-000000000001")
CHUNK_ID_TERMINATION = uuid.UUID("f0000001-0001-0001-0001-000000000002")
CHUNK_ID_PENALTY = uuid.UUID("f0000001-0001-0001-0001-000000000003")
CHUNK_ID_SKU = uuid.UUID("f0000001-0001-0001-0001-000000000004")

TEXT_PRICE = (
    "Цена договора 200 000 тенге подлежит оплате в течение 10 дней с момента подписания."
)
TEXT_TERMINATION = (
    "Расторжение договора возможно при письменном уведомлении за 14 календарных дней."
)
TEXT_PENALTY = (
    "Неустойка за просрочку исполнения обязательства составляет 0,1% за каждый день просрочки."
)
TEXT_SKU = (
    "Поставка изделия по спецификации: артикул MIL-SPEC-99X/12.3 и ГОСТ 12345-89. Приложение № 4."
)


def seed_retrieval_eval_corpus(db: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """
    Insert user, workspace, one ready document, four chunks with embeddings.

    Returns ``(workspace_id, user_id, document_id)``. Commits are left to the caller.
    """
    roles = ensure_default_roles(db)
    uid = uuid.uuid4()
    email = f"retrieval_eval_{uid.hex[:10]}@example.com"
    user = User(
        id=uid,
        email=email,
        password_hash=hash_password("RetrievalEval1!"),
        full_name="Retrieval Eval",
    )
    db.add(user)
    db.flush()

    ws = Workspace(
        id=uuid.uuid4(),
        name="Retrieval Eval WS",
        slug=f"reval-{uuid.uuid4().hex[:8]}",
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
    get_or_create_quota(db, ws.id)

    doc = Document(
        id=uuid.uuid4(),
        owner_id=user.id,
        workspace_id=ws.id,
        filename="eval_contract.txt",
        content_type="text/plain",
        storage_key="local/eval/retrieval_eval_placeholder.txt",
        status="ready",
        file_size_bytes=100,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(doc)
    db.flush()

    texts = [TEXT_PRICE, TEXT_TERMINATION, TEXT_PENALTY, TEXT_SKU]
    vecs = embed_texts(texts)
    dim = get_embedding_dim()
    chunk_specs = [
        (CHUNK_ID_PRICE, 0, texts[0], vecs[0]),
        (CHUNK_ID_TERMINATION, 1, texts[1], vecs[1]),
        (CHUNK_ID_PENALTY, 2, texts[2], vecs[2]),
        (CHUNK_ID_SKU, 3, texts[3], vecs[3]),
    ]
    repo = DocumentChunkRepository(db)
    for cid, idx, txt, vec in chunk_specs:
        if len(vec) != dim:
            raise ValueError(f"embedding dim {len(vec)} != {dim}")
        qv = "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"
        repo.insert_chunk_with_embedding(
            chunk_id=cid,
            document_id=doc.id,
            chunk_index=idx,
            text=txt,
            embedding_dim=dim,
            vector_literal=qv,
            page_number=idx + 1,
            paragraph_index=0,
        )

    return ws.id, user.id, doc.id
