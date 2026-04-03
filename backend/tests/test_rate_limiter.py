import unittest
from unittest.mock import patch

import app.services.rate_limiter as rate_limiter


class RateLimiterProductionTests(unittest.TestCase):
    def tearDown(self) -> None:
        rate_limiter._redis_client = None

    def test_production_strict_unavailable_without_redis(self) -> None:
        rate_limiter._redis_client = None
        with patch.object(rate_limiter.settings, "environment", "production"):
            with patch.object(rate_limiter.settings, "production_require_redis_rate_limiting", True):
                with patch("redis.Redis.from_url", side_effect=ConnectionError("boom")):
                    out = rate_limiter.consume_rate_limit("ip", "203.0.113.1", limit=100)
        self.assertTrue(out.unavailable)
        self.assertFalse(out.limited)

    def test_local_falls_back_to_memory_when_redis_down(self) -> None:
        rate_limiter._redis_client = None
        with patch.object(rate_limiter.settings, "environment", "local"):
            with patch("redis.Redis.from_url", side_effect=ConnectionError("boom")):
                out = rate_limiter.consume_rate_limit("ip", "203.0.113.2", limit=100)
        self.assertFalse(out.unavailable)


if __name__ == "__main__":
    unittest.main()
