"""Ingestion chunk_size / chunk_overlap validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings.ingestion import IngestionSettings


def test_chunk_overlap_must_be_less_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        IngestionSettings(chunk_size=400, chunk_overlap=400)


def test_default_chunk_settings() -> None:
    s = IngestionSettings()
    assert s.chunk_size == 800
    assert s.chunk_overlap == 200
