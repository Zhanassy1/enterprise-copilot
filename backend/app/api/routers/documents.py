import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select, text

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.schemas.documents import DocumentIngestOut, DocumentOut, DocumentSummaryOut, ReindexEmbeddingsOut
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.summary import summarize_document
from app.services.text_extraction import extract_text_from_file

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}


def _validate_upload(file: UploadFile) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower().strip()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported file extension. Allowed: pdf, docx, txt")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DbDep, user: CurrentUser) -> list[DocumentOut]:
    docs = db.scalars(select(Document).where(Document.owner_id == user.id).order_by(Document.created_at.desc())).all()
    return [DocumentOut(id=d.id, filename=d.filename, content_type=d.content_type, created_at=d.created_at) for d in docs]


@router.post("/upload", response_model=DocumentIngestOut)
def upload_document(db: DbDep, user: CurrentUser, file: UploadFile = File(...)) -> DocumentIngestOut:
    _validate_upload(file)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    orig_name = file.filename or "upload.bin"
    safe_name = f"{doc_id}_{Path(orig_name).name}"
    storage_path = upload_dir / safe_name
    file_written = False
    written_bytes = 0
    try:
        with storage_path.open("wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written_bytes += len(chunk)
                if written_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (max 25MB)")
                f.write(chunk)
        file_written = True

        extracted = extract_text_from_file(str(storage_path), content_type=file.content_type)
        if not extracted:
            raise HTTPException(status_code=400, detail="Failed to extract text (empty)")

        doc = Document(
            id=doc_id,
            owner_id=user.id,
            filename=orig_name,
            content_type=file.content_type,
            storage_path=str(storage_path).replace("\\", "/"),
            extracted_text=extracted,
        )
        db.add(doc)
        db.flush()

        chunks = chunk_text(extracted)
        vectors = embed_texts(chunks)

        chunk_rows: list[DocumentChunk] = []
        for i, t in enumerate(chunks):
            row = DocumentChunk(document_id=doc.id, chunk_index=i, text=t)
            row.embedding = None
            chunk_rows.append(row)
            db.add(row)
            db.flush()

            if i < len(vectors):
                vec = vectors[i]
                vec_lit = "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"
                db.execute(
                    text(
                        "UPDATE document_chunks SET embedding_vector = (:v)::vector(384) "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"v": vec_lit, "id": str(row.id)},
                )

        db.commit()
        db.refresh(doc)
    except HTTPException:
        if file_written:
            storage_path.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        if file_written:
            storage_path.unlink(missing_ok=True)
        raise

    return DocumentIngestOut(
        document=DocumentOut(id=doc.id, filename=doc.filename, content_type=doc.content_type, created_at=doc.created_at),
        chunks_created=len(chunk_rows),
    )


@router.post("/reindex-embeddings", response_model=ReindexEmbeddingsOut)
def reindex_embeddings(db: DbDep, user: CurrentUser) -> ReindexEmbeddingsOut:
    """Заполняет embedding_vector для chunks текущего пользователя, где он NULL (старые данные)."""
    rows = db.execute(
        text(
            """
            SELECT c.id AS id, c.text AS text
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.owner_id = CAST(:owner_id AS uuid) AND c.embedding_vector IS NULL
            """
        ),
        {"owner_id": str(user.id)},
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
def delete_document(document_id: uuid.UUID, db: DbDep, user: CurrentUser) -> dict:
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    # best-effort remove file
    try:
        if doc.storage_path and os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
    except OSError:
        pass

    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.get("/{document_id}/summary", response_model=DocumentSummaryOut)
def summarize_document_endpoint(document_id: uuid.UUID, db: DbDep, user: CurrentUser) -> DocumentSummaryOut:
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    summary = summarize_document(doc.extracted_text or "")
    return DocumentSummaryOut(document_id=doc.id, summary=summary)

