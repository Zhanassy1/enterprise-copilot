from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import IngestionJob
from app.services.document_indexing import DocumentIndexingService
from app.services.storage.base import StorageService


class IngestionWorkerService:
    def __init__(self, db_factory, storage: StorageService) -> None:
        self.db_factory = db_factory
        self.storage = storage

    def process_next(self) -> bool:
        db: Session = self.db_factory()
        try:
            now = datetime.now(UTC)
            job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.status == "pending", IngestionJob.available_at <= now)
                .order_by(IngestionJob.created_at.asc())
                .limit(1)
            )
            if not job:
                return False

            job.status = "processing"
            job.locked_at = now
            job.attempts = (job.attempts or 0) + 1
            db.add(job)
            db.flush()

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
