import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import BillingWorkspaceWriteAccess, CurrentUser, DbDep, WorkspaceReadAccess
from app.schemas.chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatReplyOut,
    ChatSessionCreateIn,
    ChatSessionOut,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[ChatSessionOut]:
    return ChatService(db).list_sessions(ws.workspace.id)


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(payload: ChatSessionCreateIn, db: DbDep, user: CurrentUser, ws: BillingWorkspaceWriteAccess) -> ChatSessionOut:
    return ChatService(db).create_session(ws.workspace.id, user.id, payload.title)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[ChatMessageOut]:
    return ChatService(db).list_messages(ws.workspace.id, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatReplyOut)
def send_message(session_id: uuid.UUID, payload: ChatMessageIn, db: DbDep, user: CurrentUser, ws: BillingWorkspaceWriteAccess) -> ChatReplyOut:
    return ChatService(db).send_message(ws.workspace.id, user.id, session_id, payload.message, payload.top_k)


@router.post("/sessions/{session_id}/messages/stream")
def send_message_stream(
    session_id: uuid.UUID,
    payload: ChatMessageIn,
    db: DbDep,
    user: CurrentUser,
    ws: BillingWorkspaceWriteAccess,
) -> StreamingResponse:
    gen = ChatService(db).iter_chat_sse(ws.workspace.id, user.id, session_id, payload.message, payload.top_k)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
