import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, WorkspaceReadAccess, WorkspaceWriteAccess
from app.core.config import settings
from app.models.document import IngestionJob
from app.schemas.documents import (
    DocumentIngestOut,
    DocumentOut,
    DocumentSummaryOut,
    IngestionJobOut,
    ReindexEmbeddingsOut,
)
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_indexing import reindex_null_embeddings_for_workspace
from app.services.audit import write_audit_from_request
from app.services.storage import get_storage_service
from app.services.summary import summarize_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[DocumentOut]:
    service = DocumentIngestionService(db, get_storage_service())
    docs = service.list_documents(ws.workspace.id)
    return [DocumentOut.from_document(d) for d in docs]


@router.post("/upload", response_model=DocumentIngestOut)
def upload_document(db: DbDep, user: CurrentUser, ws: WorkspaceWriteAccess, file: UploadFile = File(...)) -> DocumentIngestOut:
    service = DocumentIngestionService(db, get_storage_service())
    return service.upload_document(user.id, ws.workspace, file)


@router.post("/reindex-embeddings", response_model=ReindexEmbeddingsOut)
def reindex_embeddings(db: DbDep, _user: CurrentUser, ws: WorkspaceWriteAccess) -> ReindexEmbeddingsOut:
    """Backfill embedding_vector for chunks where NULL. Runs in Celery when async ingestion is enabled."""
    if settings.ingestion_async_enabled:
        from app.tasks.ingestion import reindex_workspace_embeddings_task

        async_result = reindex_workspace_embeddings_task.apply_async(
            kwargs={"workspace_id": str(ws.workspace.id)},
            queue=settings.celery_ingestion_queue,
        )
        return ReindexEmbeddingsOut(
            updated=0,
            mode="async",
            task_id=async_result.id,
            message="Reindex job queued; poll Celery result or re-run with sync (INGESTION_ASYNC_ENABLED=0) for local dev.",
        )
    n = reindex_null_embeddings_for_workspace(db, workspace_id=ws.workspace.id)
    return ReindexEmbeddingsOut(updated=n, mode="sync", message=None)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> DocumentOut:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return DocumentOut.from_document(doc)


@router.get("/{document_id}/ingestion", response_model=IngestionJobOut | None)
def get_document_ingestion_job(
    document_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess
) -> IngestionJobOut | None:
    service = DocumentIngestionService(db, get_storage_service())
    if not service.get_document(ws.workspace.id, document_id):
        raise HTTPException(status_code=404, detail="Not found")
    job = db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.document_id == document_id,
            IngestionJob.workspace_id == ws.workspace.id,
        )
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    if not job:
        return None
    return IngestionJobOut.from_job(job)


@router.get("/{document_id}/download", response_model=None)
def download_document(
    document_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess
) -> RedirectResponse | Response:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    storage = get_storage_service()
    url = storage.presigned_get_url(doc.storage_key)
    if url:
        return RedirectResponse(url)
    with storage.local_path(doc.storage_key) as local_path:
        data = Path(local_path).read_bytes()
    return Response(
        content=data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID, db: DbDep, user: CurrentUser, ws: WorkspaceWriteAccess, request: Request
) -> dict:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    write_audit_from_request(
        db,
        request,
        event_type="document.deleted",
        workspace_id=ws.workspace.id,
        user_id=user.id,
        target_type="document",
        target_id=str(doc.id),
        metadata={"filename": doc.filename},
    )
    service.delete_document(doc)
    return {"ok": True}


@router.get("/{document_id}/summary", response_model=DocumentSummaryOut)
def summarize_document_endpoint(document_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> DocumentSummaryOut:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    summary = summarize_document(doc.extracted_text or "")
    return DocumentSummaryOut(document_id=doc.id, summary=summary)

