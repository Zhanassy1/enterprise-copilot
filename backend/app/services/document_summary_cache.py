from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.document_summary_cache import DocumentSummaryCache


def advisory_lock_document_summary(db: Session, document_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(CAST(:doc_id AS text)))"),
        {"doc_id": str(document_id)},
    )


def get_cached_summary(
    db: Session,
    *,
    document_id: uuid.UUID,
    parser_version: str,
    extracted_text_hash: str,
) -> str | None:
    row = db.scalar(
        select(DocumentSummaryCache.summary).where(
            DocumentSummaryCache.document_id == document_id,
            DocumentSummaryCache.parser_version == parser_version,
            DocumentSummaryCache.extracted_text_hash == extracted_text_hash,
        )
    )
    return row


def put_cached_summary(
    db: Session,
    *,
    document_id: uuid.UUID,
    parser_version: str,
    extracted_text_hash: str,
    summary: str,
) -> None:
    stmt = (
        pg_insert(DocumentSummaryCache)
        .values(
            id=uuid.uuid4(),
            document_id=document_id,
            parser_version=parser_version,
            extracted_text_hash=extracted_text_hash,
            summary=summary,
        )
        .on_conflict_do_nothing(constraint="uq_document_summary_cache_doc_parser_hash")
    )
    db.execute(stmt)
