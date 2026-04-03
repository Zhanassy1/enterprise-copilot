from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbDep, WorkspaceReadAccess
from app.schemas.documents import SearchIn, SearchOut
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchOut)
def search(payload: SearchIn, db: DbDep, user: CurrentUser, ws: WorkspaceReadAccess) -> SearchOut:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")
    service = SearchService(db)
    return service.search(workspace_id=ws.workspace.id, user_id=user.id, query=payload.query, top_k=payload.top_k)
