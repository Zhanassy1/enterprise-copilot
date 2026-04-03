from __future__ import annotations

import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

_memory_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_redis_client = None


@dataclass(frozen=True)
class RateLimitOutcome:
    limited: bool
    limit: int
    remaining: int
    retry_after: int
    # Redis / limiter backend down in production strict mode — middleware should return 503.
    unavailable: bool = False


def _redis_rate_limit_strict() -> bool:
    env = settings.environment.lower().strip()
    return env == "production" and bool(settings.production_require_redis_rate_limiting)


def _outcome_redis_unavailable(limit: int, window_seconds: int) -> RateLimitOutcome:
    return RateLimitOutcome(
        limited=False,
        limit=limit,
        remaining=0,
        retry_after=max(1, window_seconds),
        unavailable=True,
    )


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
        except Exception as e:
            logger.debug("redis package unavailable for rate limiting: %s", e)
            if _redis_rate_limit_strict():
                logger.error("redis package required for rate limiting in production: %s", e)
            _redis_client = False
            return None
        try:
            _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            if _redis_rate_limit_strict():
                logger.error("redis connection failed for rate limiting (production strict, no in-memory fallback): %s", e)
            else:
                logger.warning("redis connection failed for rate limiting, using in-memory fallback: %s", e)
            _redis_client = False
            return None
    if _redis_client is False:
        return None
    return _redis_client


def _memory_consume(scope: str, key: str, *, limit: int, window_seconds: int) -> RateLimitOutcome:
    now = time.time()
    bucket = _memory_hits[(scope, key)]
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        oldest = bucket[0]
        retry = max(1, math.ceil(window_seconds - (now - oldest)))
        return RateLimitOutcome(True, limit, 0, retry)
    bucket.append(now)
    return RateLimitOutcome(False, limit, max(0, limit - len(bucket)), 0)


def _redis_consume(client, scope: str, key: str, *, limit: int, window_seconds: int) -> RateLimitOutcome:
    redis_key = f"rl:{scope}:{key}:{int(time.time() // window_seconds)}"
    value = int(client.incr(redis_key))
    if value == 1:
        client.expire(redis_key, window_seconds + 2)
    try:
        ttl = client.ttl(redis_key)
    except Exception as e:
        logger.debug("redis ttl for rate limit key failed: %s", e)
        ttl = -1
    retry_after = max(1, int(ttl)) if ttl is not None and ttl > 0 else window_seconds
    if value > limit:
        return RateLimitOutcome(True, limit, 0, retry_after)
    return RateLimitOutcome(False, limit, max(0, limit - value), 0)


def consume_rate_limit(scope: str, key: str, *, limit: int, window_seconds: int = 60) -> RateLimitOutcome:
    """
    Record one hit in the fixed window for ``scope``/``key`` and return limiter state.
    Empty ``key`` skips limiting (matches legacy ``is_rate_limited`` behaviour).
    """
    if not key:
        return RateLimitOutcome(False, limit, limit, 0)
    client = _get_redis()
    if client is None:
        if _redis_rate_limit_strict():
            return _outcome_redis_unavailable(limit, window_seconds)
        return _memory_consume(scope, key, limit=limit, window_seconds=window_seconds)
    try:
        return _redis_consume(client, scope, key, limit=limit, window_seconds=window_seconds)
    except Exception as e:
        if _redis_rate_limit_strict():
            logger.error("redis rate limit consume failed (production strict, no in-memory fallback): %s", e)
            return _outcome_redis_unavailable(limit, window_seconds)
        logger.warning("redis rate limit consume failed, using in-memory fallback: %s", e)
        return _memory_consume(scope, key, limit=limit, window_seconds=window_seconds)


def is_rate_limited(scope: str, key: str, *, limit: int, window_seconds: int = 60) -> bool:
    """Prefer :func:`consume_rate_limit` when building 429 responses (avoids double-counting)."""
    o = consume_rate_limit(scope, key, limit=limit, window_seconds=window_seconds)
    return o.limited or o.unavailable
