from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatMessageOut,
    ChatReplyOut,
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
from app.services.usage_metering import EVENT_CHAT_MESSAGE, EVENT_TOKENS, assert_quota, estimate_tokens, record_event


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


class ChatService:
    def __init__(self, db) -> None:
        self.db = db

    def list_sessions(self, workspace_id: uuid.UUID) -> list[ChatSessionOut]:
        rows = self.db.scalars(
            select(ChatSession).where(ChatSession.workspace_id == workspace_id).order_by(ChatSession.updated_at.desc())
        ).all()
        return [_to_session_out(x) for x in rows]

    def create_session(self, workspace_id: uuid.UUID, owner_id: uuid.UUID, title: str | None) -> ChatSessionOut:
        normalized_title = (title or "").strip() or "Новый чат"
        session = ChatSession(owner_id=owner_id, workspace_id=workspace_id, title=normalized_title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return _to_session_out(session)

    def list_messages(self, workspace_id: uuid.UUID, session_id: uuid.UUID) -> list[ChatMessageOut]:
        session = self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        rows = self.db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc())).all()
        return [_to_message_out(x) for x in rows]

    def send_message(self, workspace_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID, message: str, top_k: int) -> ChatReplyOut:
        session = self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        query_tokens = estimate_tokens(message)
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            request_increment=1,
            token_increment=query_tokens,
        )

        qvec = embed_texts([message])[0]
        hits = search_chunks_pgvector(
            self.db,
            workspace_id=workspace_id,
            query_text=message,
            query_embedding=qvec,
            top_k=top_k,
        )
        decision, confidence = decide_response_mode(
            message,
            hits,
            answer_threshold=settings.answer_threshold,
            clarify_threshold=settings.clarify_threshold,
        )
        details: str | None = None
        clarifying_question: str | None = None
        if decision == "answer":
            answer = build_answer(message, hits)
            details = "Ответ подтвержден найденными фрагментами документов."
        else:
            answer = ""
            clarifying_question = build_clarifying_question(message)
        next_step = build_next_step(decision)
        assistant_content = compose_response_text(
            decision=decision,
            answer=answer,
            details=details,
            clarifying_question=clarifying_question,
            next_step=next_step,
        )
        output_tokens = estimate_tokens(assistant_content)
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            token_increment=output_tokens,
        )

        user_msg = ChatMessage(session_id=session.id, role="user", content=message, sources_json="[]")
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            sources_json=json.dumps(hits, ensure_ascii=False, default=str),
        )
        self.db.add(user_msg)
        self.db.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_CHAT_MESSAGE,
            quantity=1,
            unit="count",
            metadata={"session_id": str(session.id), "top_k": int(top_k)},
        )
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_TOKENS,
            quantity=query_tokens + output_tokens,
            unit="tokens",
            metadata={"scope": "chat", "session_id": str(session.id)},
        )
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(user_msg)
        self.db.refresh(assistant_msg)

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
