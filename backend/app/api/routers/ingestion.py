from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DbDep, WorkspaceReadAccess
from app.constants.ingestion import INGESTION_JOB_STATUSES
from app.models.document import IngestionJob
from app.schemas.documents import IngestionJobOut

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/jobs", response_model=list[IngestionJobOut])
def list_ingestion_jobs(
    db: DbDep,
    ws: WorkspaceReadAccess,
    status: str | None = Query(
        default=None,
        description="Filter by job status (canonical), or dead_letter for dead-letter queue.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[IngestionJobOut]:
    """List ingestion jobs for the current workspace (e.g. failed / dead-letter triage)."""
    q = select(IngestionJob).where(IngestionJob.workspace_id == ws.workspace.id)
    if status:
        st = status.strip().lower()
        if st == "dead_letter":
            q = q.where(IngestionJob.dead_lettered_at.is_not(None))
        else:
            if st not in INGESTION_JOB_STATUSES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid status filter; expected one of {list(INGESTION_JOB_STATUSES)} or dead_letter",
                )
            q = q.where(IngestionJob.status == st)
    q = q.order_by(IngestionJob.created_at.desc()).limit(limit)
    rows = db.scalars(q).all()
    return [IngestionJobOut.from_job(j) for j in rows]
