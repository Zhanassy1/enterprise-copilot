"""Unit tests for SQLAlchemy engine kwargs (no live Postgres)."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.pool import NullPool

from app.db.session import build_engine_kwargs


def _ns(**kwargs: object) -> SimpleNamespace:
    base = {
        "db_connect_timeout": 10,
        "app_name": "acme",
        "db_application_name": "",
        "db_pool_size": 5,
        "db_max_overflow": 10,
        "db_pool_recycle": 1800,
        "db_pool_timeout": 30,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_build_engine_kwargs_queue_pool() -> None:
    s = _ns()
    k = build_engine_kwargs(s, use_nullpool=False)
    assert k["pool_pre_ping"] is True
    assert k["connect_args"]["connect_timeout"] == 10
    assert k["connect_args"]["application_name"] == "acme"
    assert k["pool_size"] == 5
    assert k["max_overflow"] == 10
    assert k["pool_timeout"] == 30
    assert k["pool_recycle"] == 1800
    assert "poolclass" not in k


def test_build_engine_kwargs_no_recycle_when_zero() -> None:
    s = _ns(db_pool_recycle=0)
    k = build_engine_kwargs(s, use_nullpool=False)
    assert "pool_recycle" not in k


def test_build_engine_kwargs_application_name_override() -> None:
    s = _ns(db_application_name="worker-celery")
    k = build_engine_kwargs(s, use_nullpool=False)
    assert k["connect_args"]["application_name"] == "worker-celery"


def test_build_engine_kwargs_nullpool() -> None:
    s = _ns()
    k = build_engine_kwargs(s, use_nullpool=True)
    assert k["poolclass"] is NullPool
    assert "pool_size" not in k


def test_build_engine_kwargs_truncate_application_name() -> None:
    long = "x" * 100
    s = _ns(db_application_name=long)
    k = build_engine_kwargs(s, use_nullpool=False)
    assert len(k["connect_args"]["application_name"]) == 64
