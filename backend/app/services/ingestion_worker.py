from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.document import IngestionJob
from app.services.document_indexing import DocumentIndexingService
from app.services.ingestion_job_claim import claim_next_poll_job
from app.services.storage.base import StorageService


class IngestionWorkerService:
    def __init__(self, db_factory, storage: StorageService) -> None:
        self.db_factory = db_factory
        self.storage = storage

    def process_next(self) -> bool:
        db: Session = self.db_factory()
        try:
            now = datetime.now(UTC)
            job_id = claim_next_poll_job(db, now=now)
            if not job_id:
                return False

            job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.id == job_id)
                .options(selectinload(IngestionJob.document))
            )
            if not job or job.document is None:
                return False

            try:
                indexer = DocumentIndexingService(db, self.storage)
                indexer.run(job.document)
                job.status = "done"
                job.error_message = None
                job.completed_at = datetime.now(UTC)
                db.add(job)
                db.commit()
                return True
            except Exception as exc:
                max_attempts = int(settings.ingestion_max_attempts)
                if job.attempts >= max_attempts:
                    job.status = "failed"
                    job.error_message = str(exc)
                    job.completed_at = datetime.now(UTC)
                else:
                    job.status = "pending"
                    job.error_message = str(exc)
                    job.available_at = datetime.now(UTC)
                    job.locked_at = None
                db.add(job)
                db.commit()
                return True
        finally:
            db.close()

    def run_forever(self) -> None:
        while True:
            processed = self.process_next()
            if not processed:
                time.sleep(float(settings.ingestion_worker_poll_seconds))
