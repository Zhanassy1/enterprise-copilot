import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import text

from app.api.deps import CurrentUser, DbDep, WorkspaceReadAccess, WorkspaceWriteAccess
from app.models.document import DocumentChunk
from app.schemas.documents import DocumentIngestOut, DocumentOut, DocumentSummaryOut, ReindexEmbeddingsOut
from app.services.document_ingestion import DocumentIngestionService, validate_upload
from app.services.embeddings import embed_texts
from app.services.audit import write_audit_log
from app.services.storage import get_storage_service
from app.services.summary import summarize_document

router = APIRouter(prefix="/documents", tags=["documents"])

def _validate_upload(file: UploadFile) -> None:
    validate_upload(file)


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
    """Заполняет embedding_vector для chunks текущего workspace, где он NULL (старые данные)."""
    rows = db.execute(
        text(
            """
            SELECT c.id AS id, c.text AS text
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = CAST(:workspace_id AS uuid) AND c.embedding_vector IS NULL
            """
        ),
        {"workspace_id": str(ws.workspace.id)},
    ).mappings().all()
    if not rows:
        return ReindexEmbeddingsOut(updated=0)

    texts = [str(r["text"]) for r in rows]
    ids = [str(r["id"]) for r in rows]
    vectors = embed_texts(texts)
    if len(vectors) != len(ids):
        raise HTTPException(status_code=500, detail="Embedding count mismatch")

    for cid, vec in zip(ids, vectors, strict=True):
        vec_lit = "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"
        db.execute(
            text(
                "UPDATE document_chunks SET embedding_vector = (:v)::vector(384) "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"v": vec_lit, "id": cid},
        )
    db.commit()
    return ReindexEmbeddingsOut(updated=len(ids))


@router.delete("/{document_id}")
def delete_document(document_id: uuid.UUID, db: DbDep, user: CurrentUser, ws: WorkspaceWriteAccess) -> dict:
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

