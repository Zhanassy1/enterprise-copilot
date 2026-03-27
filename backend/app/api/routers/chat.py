import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, WorkspaceReadAccess, WorkspaceWriteAccess
from app.schemas.chat import (
    ChatMessageIn,
    ChatReplyOut,
    ChatSessionCreateIn,
    ChatSessionOut,
    ChatMessageOut,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[ChatSessionOut]:
    return ChatService(db).list_sessions(ws.workspace.id)


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(payload: ChatSessionCreateIn, db: DbDep, user: CurrentUser, ws: WorkspaceWriteAccess) -> ChatSessionOut:
    return ChatService(db).create_session(ws.workspace.id, user.id, payload.title)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[ChatMessageOut]:
    return ChatService(db).list_messages(ws.workspace.id, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatReplyOut)
def send_message(session_id: uuid.UUID, payload: ChatMessageIn, db: DbDep, user: CurrentUser, ws: WorkspaceWriteAccess) -> ChatReplyOut:
    return ChatService(db).send_message(ws.workspace.id, user.id, session_id, payload.message, payload.top_k)
