import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.documents import AnswerStyle, SearchHit


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sources: list[SearchHit] = []
    created_at: datetime
    details: str | None = None
    next_step: str | None = None
    clarifying_question: str | None = None
    decision: Literal["answer", "clarify", "insufficient_context"] | None = None
    answer_style: AnswerStyle | None = None


class ChatMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    answer_style: AnswerStyle | None = Field(
        default=None,
        description="concise: короткая выдержка; narrative: связный ответ по фрагментам",
    )

    @field_validator("message", mode="after")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


class ChatReplyOut(BaseModel):
    session: ChatSessionOut
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    decision: Literal["answer", "clarify", "insufficient_context"] = "answer"
    confidence: float = 0.0
    details: str | None = None
    clarifying_question: str | None = None
    next_step: str | None = None
    evidence_collapsed_by_default: bool = True
    answer_style: AnswerStyle = "concise"
