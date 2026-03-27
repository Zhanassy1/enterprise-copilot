from __future__ import annotations

from collections import defaultdict, deque
import time

from app.core.config import settings

_memory_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
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
            _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
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
