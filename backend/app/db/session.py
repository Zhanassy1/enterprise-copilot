import logging
import os
import time
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.pool_metrics import record_pool_checkout, record_session_acquire

if TYPE_CHECKING:
    from app.core.config import Settings

_log = logging.getLogger("app.db")

def _application_name(s: "Settings") -> str:
    raw = (s.db_application_name or s.app_name or "enterprise-copilot").strip() or "enterprise-copilot"
    return raw[:64]


def build_engine_kwargs(
    s: "Settings", *, use_nullpool: bool | None = None
) -> dict[str, Any]:
    """Assemble `create_engine` keyword arguments (for tests and `create_engine`)."""
    nlp = (
        (os.environ.get("SQLALCHEMY_USE_NULLPOOL") == "1")
        if use_nullpool is None
        else use_nullpool
    )
    out: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": int(s.db_connect_timeout),
            "application_name": _application_name(s),
        },
    }
    if nlp:
        out["poolclass"] = NullPool
        return out
    out["pool_size"] = int(s.db_pool_size)
    out["max_overflow"] = int(s.db_max_overflow)
    out["pool_timeout"] = int(s.db_pool_timeout)
    if int(s.db_pool_recycle) > 0:
        out["pool_recycle"] = int(s.db_pool_recycle)
    return out


def _configure_dbapi_connection(dbapi_connection: object, s: "Settings") -> None:
    """Run after new DB connection: session GUCs and pgvector type registration."""
    st_ms = int(s.db_statement_timeout_ms)
    if st_ms > 0:
        with dbapi_connection.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (f"{st_ms}ms",))
    idle_ms = int(s.db_idle_in_transaction_session_timeout_ms)
    if idle_ms > 0:
        with dbapi_connection.cursor() as cur:
            cur.execute("SET idle_in_transaction_session_timeout = %s", (f"{idle_ms}ms",))
    register_vector(dbapi_connection)


def _make_engine() -> Any:
    eng = create_engine(settings.database_url, **build_engine_kwargs(settings))

    @event.listens_for(eng, "connect")
    def _on_engine_connect(dbapi_connection: object, _connection_record: object) -> None:
        _configure_dbapi_connection(dbapi_connection, settings)

    if settings.db_pool_metrics_enabled:
        @event.listens_for(eng.pool, "checkout")
        def _on_pool_checkout(
            _dbapi_connection: object,
            _connection_record: object,
            _connection_proxy: object,
        ) -> None:
            record_pool_checkout()

    return eng


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    t0 = time.perf_counter()
    db = SessionLocal()
    dt_ms = (time.perf_counter() - t0) * 1000.0
    if settings.db_pool_metrics_enabled:
        record_session_acquire(
            elapsed_ms=dt_ms,
            slow_threshold_ms=float(settings.db_checkout_warn_ms),
            count_slow=True,
        )
    if (
        float(settings.db_checkout_warn_ms) > 0
        and dt_ms >= float(settings.db_checkout_warn_ms)
    ):
        _log.warning(
            "db session acquire took %.1fms (threshold %.1fms)",
            dt_ms,
            float(settings.db_checkout_warn_ms),
        )
    try:
        yield db
    finally:
        db.close()
