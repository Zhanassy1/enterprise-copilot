import unittest
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.usage_metering import (
    TOKEN_EVENT_TYPES_FOR_MONTHLY_CAP,
    assert_quota,
    effective_rate_limits_for_plan,
    estimate_tokens,
    month_window,
)


class UsageMeteringTests(unittest.TestCase):
    def test_month_window_bounds(self) -> None:
        dt = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)
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

    def test_assert_quota_token_check_uses_all_metered_event_types(self) -> None:
        quota = SimpleNamespace(
            monthly_request_limit=1_000_000,
            monthly_token_limit=1_000_000,
            monthly_upload_bytes_limit=1_000_000,
            max_documents=100,
        )
        captured: list[tuple[str, ...]] = []

        def capture_sum(_db, *, workspace_id, event_types, unit, from_dt, to_dt):
            captured.append(tuple(event_types))
            return 0

        with patch("app.services.usage_metering.get_or_create_quota", return_value=quota), patch(
            "app.services.usage_metering._sum_events", side_effect=capture_sum
        ):
            assert_quota(
                db=MagicMock(),
                workspace_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                token_increment=1,
            )
        self.assertEqual(captured[-1], TOKEN_EVENT_TYPES_FOR_MONTHLY_CAP)

    def test_assert_quota_raises_on_token_limit(self) -> None:
        quota = SimpleNamespace(
            monthly_request_limit=1_000_000,
            monthly_token_limit=100,
            monthly_upload_bytes_limit=1_000_000,
            max_documents=100,
        )
        with patch("app.services.usage_metering.get_or_create_quota", return_value=quota), patch(
            "app.services.usage_metering._sum_events", return_value=100
        ):
            with self.assertRaises(HTTPException) as err:
                assert_quota(
                    db=MagicMock(),
                    workspace_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    token_increment=1,
                )
            self.assertEqual(err.exception.status_code, 429)
            self.assertIn("token", (err.exception.detail or "").lower())

    def test_assert_quota_raises_on_rerank_limit(self) -> None:
        quota = SimpleNamespace(
            plan_slug="free",
            monthly_request_limit=1_000_000,
            monthly_token_limit=1_000_000,
            monthly_upload_bytes_limit=1_000_000,
            max_documents=100,
        )
        with patch("app.services.usage_metering.get_or_create_quota", return_value=quota), patch(
            "app.services.usage_metering._sum_events",
            return_value=2000,
        ):
            with self.assertRaises(HTTPException) as err:
                assert_quota(
                    db=MagicMock(),
                    workspace_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    rerank_increment=1,
                )
            self.assertEqual(err.exception.status_code, 429)
            self.assertIn("rerank", (err.exception.detail or "").lower())

    def test_plan_defaults_include_concurrent_job_cap(self) -> None:
        from app.services.usage_metering import PLAN_LIMITS

        self.assertEqual(PLAN_LIMITS["free"]["max_concurrent_ingestion_jobs"], 2)
        self.assertEqual(PLAN_LIMITS["team"]["max_concurrent_ingestion_jobs"], 32)

    def test_effective_rate_limits_scales_by_plan(self) -> None:
        free = effective_rate_limits_for_plan("free")
        team = effective_rate_limits_for_plan("team")
        self.assertGreater(team["per_user"], free["per_user"])
        self.assertGreater(team["per_ip"], free["per_ip"])
        self.assertGreater(team["rag_user"], free["rag_user"])


if __name__ == "__main__":
    unittest.main()
