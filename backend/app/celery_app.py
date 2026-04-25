import logging

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.startup_checks import validate_settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "enterprise_copilot",
    broker=settings.celery_broker,
    backend=settings.celery_result_backend,
    include=["app.tasks.ingestion", "app.tasks.maintenance"],
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
    beat_schedule={
        "purge-soft-deleted-documents-daily": {
            "task": "maintenance.purge_soft_deleted_documents",
            "schedule": crontab(hour=3, minute=17),
            "options": {"queue": settings.celery_ingestion_queue},
        },
        "process-usage-outbox-minutely": {
            "task": "maintenance.process_usage_outbox",
            "schedule": crontab(minute="*"),
            "options": {"queue": settings.celery_ingestion_queue},
        },
        "requeue-stale-ingestion-every-5m": {
            "task": "maintenance.requeue_stale_ingestion_jobs",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": settings.celery_ingestion_queue},
        },
    },
    # Security: reject pickle/or other unsafe serializers (Celery recommendation for untrusted brokers).
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    event_serializer="json",
)

validate_settings(settings)

try:
    from celery.signals import worker_process_init

    @worker_process_init.connect
    def _celery_init_sentry(**_kwargs) -> None:
        if settings.sentry_dsn:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=float(settings.sentry_traces_sample_rate),
            )
except Exception as e:
    logger.warning("celery worker_process_init / sentry hook registration failed: %s", e)
