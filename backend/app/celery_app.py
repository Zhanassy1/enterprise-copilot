from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "enterprise_copilot",
    broker=settings.celery_broker,
    backend=settings.celery_result_backend,
    include=["app.tasks.ingestion"],
)

celery_app.conf.update(
    task_default_queue=settings.celery_ingestion_queue,
    task_track_started=settings.celery_task_track_started,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    task_acks_late=settings.celery_task_acks_late,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
    timezone="UTC",
    enable_utc=True,
)
