"""Shared Redis connectivity check (startup, readiness)."""

from __future__ import annotations


def ping_redis_url(url: str, *, socket_connect_timeout: float = 3.0) -> None:
    """Raise on failure. Does not log URLs (may contain credentials)."""
    import redis

    client = redis.Redis.from_url(
        url.strip(),
        decode_responses=True,
        socket_connect_timeout=socket_connect_timeout,
    )
    client.ping()
