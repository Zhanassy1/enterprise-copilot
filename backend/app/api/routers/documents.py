import hashlib
import uuid

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from app.api.deps import (
    BillingWorkspaceWriteAccess,
    CurrentUser,
    DbDep,
    WorkspaceReadAccess,
    role_rank,
)
from app.core.config import settings
from app.models.document import IngestionJob
from app.schemas.common_api import EmptyJSONBody
from app.schemas.documents import (
    DocumentIngestOut,
    DocumentOut,
    DocumentSummaryOut,
    IngestionJobOut,
    ReindexEmbeddingsOut,
)
from app.services.audit import write_audit_log
from app.services.document_indexing import reindex_null_embeddings_for_workspace
from app.services.document_ingestion import DocumentIngestionService, validate_upload
from app.services.document_summary_cache import (
    advisory_lock_document_summary,
    get_cached_summary,
    put_cached_summary,
)
from app.services.llm import estimate_summary_prompt_tokens, llm_enabled, llm_summarize
from app.services.storage import get_storage_service
from app.services.summary import summarize_document
from app.services.usage_metering import (
    EVENT_EMBEDDING_TOKENS,
    EVENT_GENERATION_TOKENS,
    EVENT_SUMMARY_GENERATION,
    assert_quota,
    record_event,
)

router = APIRouter(prefix="/documents", tags=["documents"])

def _validate_upload(file: UploadFile) -> None:
    validate_upload(file)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> list[DocumentOut]:
    service = DocumentIngestionService(db, get_storage_service())
    pairs = service.list_documents(ws.workspace.id)
    return [DocumentOut.from_document(d, ingestion_job_status=js) for d, js in pairs]


@router.post("/upload", response_model=DocumentIngestOut)
def upload_document(db: DbDep, user: CurrentUser, ws: BillingWorkspaceWriteAccess, file: UploadFile = File(...)) -> DocumentIngestOut:
    service = DocumentIngestionService(db, get_storage_service())
    return service.upload_document(user.id, ws.workspace, file)


@router.post("/reindex-embeddings", response_model=ReindexEmbeddingsOut)
def reindex_embeddings(
    db: DbDep,
    _user: CurrentUser,
    ws: BillingWorkspaceWriteAccess,
    _body: EmptyJSONBody | None = Body(default=None),
) -> ReindexEmbeddingsOut:
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
    if settings.environment.lower().strip() == "production":
        raise HTTPException(
            status_code=503,
            detail="Synchronous reindex is not available in production; keep INGESTION_ASYNC_ENABLED=1 and use the queued task.",
        )
    n = reindex_null_embeddings_for_workspace(db, workspace_id=ws.workspace.id)
    return ReindexEmbeddingsOut(updated=n, mode="sync", message=None)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: DbDep, _user: CurrentUser, ws: WorkspaceReadAccess) -> DocumentOut:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    js = service.latest_ingestion_job_status(ws.workspace.id, document_id)
    return DocumentOut.from_document(doc, ingestion_job_status=js)


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
    return storage.direct_download_response(
        doc.storage_key,
        filename=doc.filename,
        content_type=doc.content_type,
    )


@router.delete("/{document_id}")
def delete_document(document_id: uuid.UUID, db: DbDep, user: CurrentUser, ws: BillingWorkspaceWriteAccess) -> dict:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    write_audit_log(
        db,
        event_type="document.deleted",
        workspace_id=ws.workspace.id,
        user_id=user.id,
        target_type="document",
        target_id=str(doc.id),
        metadata={"filename": doc.filename},
    )
    service.delete_document(doc, ws.workspace.id)
    return {"ok": True}


@router.get("/{document_id}/summary", response_model=DocumentSummaryOut)
def summarize_document_endpoint(document_id: uuid.UUID, db: DbDep, user: CurrentUser, ws: WorkspaceReadAccess) -> DocumentSummaryOut:
    service = DocumentIngestionService(db, get_storage_service())
    doc = service.get_document(ws.workspace.id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    raw = doc.extracted_text or ""
    if not raw.strip():
        summary = summarize_document(raw, allow_llm=False)
        return DocumentSummaryOut(document_id=doc.id, summary=summary)
    text_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    parser_ver = doc.parser_version or ""

    cached = get_cached_summary(
        db,
        document_id=doc.id,
        parser_version=parser_ver,
        extracted_text_hash=text_hash,
    )
    if cached is not None:
        return DocumentSummaryOut(document_id=doc.id, summary=cached)

    role_name = ws.membership.role.name if ws.membership.role else None
    can_llm = (role_rank(role_name) or 0) >= (role_rank("member") or 0)
    if not can_llm or not llm_enabled():
        summary = summarize_document(raw, allow_llm=False)
        return DocumentSummaryOut(document_id=doc.id, summary=summary)

    advisory_lock_document_summary(db, doc.id)
    cached_after_lock = get_cached_summary(
        db,
        document_id=doc.id,
        parser_version=parser_ver,
        extracted_text_hash=text_hash,
    )
    if cached_after_lock is not None:
        return DocumentSummaryOut(document_id=doc.id, summary=cached_after_lock)

    prompt_est = estimate_summary_prompt_tokens(raw)
    assert_quota(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        summary_generation_increment=1,
    )
    assert_quota(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        token_increment=prompt_est,
    )
    summary_text, prompt_tok, completion_tok = llm_summarize(raw)
    if not summary_text:
        summary_text = summarize_document(raw, allow_llm=False)
        return DocumentSummaryOut(document_id=doc.id, summary=summary_text)

    assert_quota(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        token_increment=completion_tok,
    )
    record_event(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        event_type=EVENT_SUMMARY_GENERATION,
        quantity=1,
        unit="count",
        metadata={"document_id": str(doc.id)},
    )
    record_event(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        event_type=EVENT_EMBEDDING_TOKENS,
        quantity=prompt_tok,
        unit="tokens",
        metadata={"scope": "document_summary", "document_id": str(doc.id)},
    )
    record_event(
        db,
        workspace_id=ws.workspace.id,
        user_id=user.id,
        event_type=EVENT_GENERATION_TOKENS,
        quantity=completion_tok,
        unit="tokens",
        metadata={"scope": "document_summary", "document_id": str(doc.id)},
    )
    put_cached_summary(
        db,
        document_id=doc.id,
        parser_version=parser_ver,
        extracted_text_hash=text_hash,
        summary=summary_text,
    )
    db.commit()
    return DocumentSummaryOut(document_id=doc.id, summary=summary_text)

