import logging

from fastapi import FastAPI
from fastapi.responses import Response
from sqlalchemy import distinct, func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.db.pool_metrics import get_db_pool_metrics_state
from app.middleware.metrics import get_metrics_state
from app.middleware.rerank_metrics import get_rerank_metrics_state
from app.models.document import Document, DocumentChunk, IngestionJob


def init_sentry(settings: Settings, log: logging.Logger | None = None) -> None:
    log = log or logging.getLogger("app.request")
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=float(settings.sentry_traces_sample_rate),
            environment=settings.environment,
        )
    except Exception as e:
        log.exception("Failed to initialize sentry: %s", e)


def register_metrics_route(app: FastAPI, settings: Settings, log: logging.Logger | None = None) -> None:
    log = log or logging.getLogger("app.request")

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        if not settings.observability_metrics_enabled:
            return Response(status_code=404)
        _metrics_counter, _metrics_latency_sum_ms = get_metrics_state()
        lines: list[str] = []
        for key, value in sorted(_metrics_counter.items()):
            method, path, status = key
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {int(value)}'
            )
        for key, value in sorted(_metrics_latency_sum_ms.items()):
            method, path = key
            lines.append(f'http_request_latency_ms_sum{{method="{method}",path="{path}"}} {float(value):.4f}')
        rr_calls, rr_latency_sum, rr_timeouts = get_rerank_metrics_state()
        lines.append(f"rerank_calls_total {int(rr_calls)}")
        lines.append(f"rerank_latency_ms_sum {float(rr_latency_sum):.4f}")
        lines.append(f"rerank_timeouts_total {int(rr_timeouts)}")
        co_total, sa_total, sa_ms_sum, sa_slow = get_db_pool_metrics_state()
        lines.append(f"db_pool_checkout_total {int(co_total)}")
        lines.append(f"db_session_acquire_total {int(sa_total)}")
        lines.append(f"db_session_acquire_ms_sum {float(sa_ms_sum):.4f}")
        lines.append(f"db_session_slow_acquire_total {int(sa_slow)}")
        try:
            from app.tasks import ingestion as _ing_metrics

            lines.append(f"celery_ingestion_terminal_failures_total {_ing_metrics.ingestion_terminal_failures_total}")
            lines.append(f"celery_ingestion_retries_total {_ing_metrics.ingestion_retries_total}")
        except Exception as e:
            log.debug("metrics: optional ingestion counters unavailable: %s", e)
        try:
            db = SessionLocal()
            try:
                rows = db.execute(
                    select(IngestionJob.status, func.count(IngestionJob.id)).group_by(IngestionJob.status)
                ).all()
                for st, cnt in rows:
                    lines.append(f'ingestion_jobs_total{{status="{st}"}} {int(cnt)}')
                n_null = db.scalar(
                    select(func.count(distinct(Document.id)))
                    .select_from(Document)
                    .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                    .where(
                        Document.deleted_at.is_(None),
                        DocumentChunk.embedding_vector.is_(None),
                    )
                )
                lines.append(f"documents_with_null_embeddings {int(n_null or 0)}")
            finally:
                db.close()
        except Exception as e:
            log.debug("metrics: ingestion job counts query failed: %s", e)
        body = "\n".join(lines) + ("\n" if lines else "")
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
