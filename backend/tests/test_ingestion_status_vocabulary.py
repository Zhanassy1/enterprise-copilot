"""Contract: pipeline status strings match frontend/src/lib/ingestion-statuses.ts (PIPELINE_JOB_STATUSES)."""

from app.constants.ingestion import DOCUMENT_PIPELINE_STATUSES, INGESTION_JOB_STATUSES

_EXPECTED = ("queued", "processing", "retrying", "ready", "failed")


def test_ingestion_job_statuses_tuples_match_contract() -> None:
    assert INGESTION_JOB_STATUSES == _EXPECTED
    assert DOCUMENT_PIPELINE_STATUSES == _EXPECTED
