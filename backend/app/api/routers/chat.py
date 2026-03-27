import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatReplyOut,
    ChatSessionCreateIn,
    ChatSessionOut,
)
from app.schemas.documents import SearchHit
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer,
    build_clarifying_question,
    build_next_step,
    compose_response_text,
    decide_response_mode,
)
from app.services.vector_search import search_chunks_pgvector

router = APIRouter(prefix="/chat", tags=["chat"])


def _to_session_out(session: ChatSession) -> ChatSessionOut:
    return ChatSessionOut(id=session.id, title=session.title, created_at=session.created_at, updated_at=session.updated_at)


def _to_message_out(message: ChatMessage) -> ChatMessageOut:
    raw = message.sources_json or "[]"
    try:
        loaded = json.loads(raw)
        sources = [SearchHit(**x) for x in loaded if isinstance(x, dict)]
    except Exception:
        sources = []
    return ChatMessageOut(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        sources=sources,
        created_at=message.created_at,
    )


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: DbDep, user: CurrentUser) -> list[ChatSessionOut]:
    rows = db.scalars(select(ChatSession).where(ChatSession.owner_id == user.id).order_by(ChatSession.updated_at.desc())).all()
    return [_to_session_out(x) for x in rows]


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(payload: ChatSessionCreateIn, db: DbDep, user: CurrentUser) -> ChatSessionOut:
    title = (payload.title or "").strip() or "Новый чат"
    session = ChatSession(owner_id=user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_session_out(session)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: DbDep, user: CurrentUser) -> list[ChatMessageOut]:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == user.id))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc())).all()
    return [_to_message_out(x) for x in rows]


@router.post("/sessions/{session_id}/messages", response_model=ChatReplyOut)
def send_message(session_id: uuid.UUID, payload: ChatMessageIn, db: DbDep, user: CurrentUser) -> ChatReplyOut:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == user.id))
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    qvec = embed_texts([payload.message])[0]
    hits = search_chunks_pgvector(
        db,
        owner_id=user.id,
        query_text=payload.message,
        query_embedding=qvec,
        top_k=payload.top_k,
    )
    decision, confidence = decide_response_mode(
        payload.message,
        hits,
        answer_threshold=settings.answer_threshold,
        clarify_threshold=settings.clarify_threshold,
    )
    details: str | None = None
    clarifying_question: str | None = None
    if decision == "answer":
        answer = build_answer(payload.message, hits)
        details = "Ответ подтвержден найденными фрагментами документов."
    else:
        answer = ""
        clarifying_question = build_clarifying_question(payload.message)
    next_step = build_next_step(decision)
    assistant_content = compose_response_text(
        decision=decision,
        answer=answer,
        details=details,
        clarifying_question=clarifying_question,
        next_step=next_step,
    )

    user_msg = ChatMessage(session_id=session.id, role="user", content=payload.message, sources_json="[]")
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        sources_json=json.dumps(hits, ensure_ascii=False, default=str),
    )
    db.add(user_msg)
    db.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return ChatReplyOut(
        session=_to_session_out(session),
        user_message=_to_message_out(user_msg),
        assistant_message=_to_message_out(assistant_msg),
        decision=decision,
        confidence=confidence,
        details=details,
        clarifying_question=clarifying_question,
        next_step=next_step,
        evidence_collapsed_by_default=True,
    )
