from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from app.core.config import settings

_memory_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_memory_sliding: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_redis_client = None


def _memory_hit(scope: str, key: str, *, limit: int, window_seconds: int = 60) -> bool:
    now = time.time()
    bucket = _memory_hits[(scope, key)]
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
        except Exception:
            _redis_client = False
            return None
        try:
            _redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=float(settings.redis_socket_connect_timeout_seconds),
                socket_timeout=float(settings.redis_socket_timeout_seconds),
            )
            _redis_client.ping()
        except Exception:
            _redis_client = False
            return None
    if _redis_client is False:
        return None
    return _redis_client


def is_rate_limited(scope: str, key: str, *, limit: int, window_seconds: int = 60) -> bool:
    if not key:
        return False
    client = _get_redis()
    if client is None:
        return _memory_hit(scope, key, limit=limit, window_seconds=window_seconds)
    redis_key = f"rl:{scope}:{key}:{int(time.time() // window_seconds)}"
    try:
        value = int(client.incr(redis_key))
        if value == 1:
            client.expire(redis_key, window_seconds + 2)
        return value > limit
    except Exception:
        return _memory_hit(scope, key, limit=limit, window_seconds=window_seconds)


def _memory_sliding_hit(scope: str, key: str, *, limit: int, window_seconds: int) -> bool:
    now = time.time()
    bucket = _memory_sliding[(scope, key)]
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def is_sliding_rate_limited(scope: str, key: str, *, limit: int, window_seconds: int) -> bool:
    """Redis sliding-window counter; falls back to in-process deque when Redis is unavailable."""
    if not key:
        return False
    client = _get_redis()
    if client is None:
        return _memory_sliding_hit(scope, key, limit=limit, window_seconds=window_seconds)
    rkey = f"rlsw:{scope}:{key}"
    now = time.time()
    try:
        pipe = client.pipeline(transaction=True)
        pipe.zremrangebyscore(rkey, 0, now - window_seconds)
        pipe.zcard(rkey)
        _rems, count = pipe.execute()
        if int(count) >= limit:
            return True
        client.zadd(rkey, {str(uuid.uuid4()): now})
        client.expire(rkey, window_seconds + 2)
        return False
    except Exception:
        return _memory_sliding_hit(scope, key, limit=limit, window_seconds=window_seconds)


def enforce_auth_email_rate_limit(email: str) -> None:
    key = (email or "").strip().lower()
    if not key:
        return
    if is_sliding_rate_limited(
        "auth_email",
        key,
        limit=int(settings.rate_limit_auth_email_limit),
        window_seconds=int(settings.rate_limit_auth_email_window_seconds),
    ):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this email")
