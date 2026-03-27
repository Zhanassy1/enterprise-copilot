import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.services.usage_metering import assert_quota, estimate_tokens, month_window


class UsageMeteringTests(unittest.TestCase):
    def test_month_window_bounds(self) -> None:
        dt = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        start, end = month_window(dt)
        self.assertEqual(start.isoformat(), "2026-03-01T00:00:00+00:00")
        self.assertEqual(end.isoformat(), "2026-04-01T00:00:00+00:00")

    def test_estimate_tokens_non_empty(self) -> None:
        self.assertGreater(estimate_tokens("contract price 100 kzt"), 0)

    def test_assert_quota_raises_on_request_limit(self) -> None:
        quota = SimpleNamespace(
            monthly_request_limit=2,
            monthly_token_limit=1_000_000,
            monthly_upload_bytes_limit=1_000_000,
        )
        with patch("app.services.usage_metering.get_or_create_quota", return_value=quota), patch(
            "app.services.usage_metering._sum_events", return_value=2
        ):
            with self.assertRaises(HTTPException) as err:
                assert_quota(
                    db=SimpleNamespace(),
                    workspace_id="00000000-0000-0000-0000-000000000000",
                    request_increment=1,
                )
            self.assertEqual(err.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
