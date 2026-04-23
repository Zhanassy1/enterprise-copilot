"""Build answer with provenance + optional citation index map (no LLM by default)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.nlp import build_answer_with_provenance, suggest_citation_index_to_chunk


def test_build_answer_with_provenance_empty_hits() -> None:
    t, p = build_answer_with_provenance("q", [], extractive_only=True)
    assert "не найдено" in t.lower() or "не найден" in t.lower()
    assert p == []


def test_suggest_citation_index_to_chunk_maps_brackets() -> None:
    cid1 = uuid.uuid4()
    cid2 = uuid.uuid4()
    hits = [
        {"chunk_id": cid1, "text": "first"},
        {"chunk_id": cid2, "text": "second"},
    ]
    s = f"One [1] and [2] ref."
    m = suggest_citation_index_to_chunk(s, hits)
    assert m is not None
    assert m["1"] == str(cid1)
    assert m["2"] == str(cid2)


def test_suggest_citation_index_none_without_brackets() -> None:
    hits = [{"chunk_id": uuid.uuid4(), "text": "a"}]
    assert suggest_citation_index_to_chunk("no markers here", hits) is None


def test_provenance_includes_top_hit() -> None:
    cid = uuid.UUID("f0000001-0001-0001-0001-000000000001")
    hits = [
        {
            "chunk_id": cid,
            "text": "Цена договора 200 000 тенге подлежит оплате в течение 10 дней с момента подписания.",
        }
    ]
    with patch.object(settings, "llm_api_key", ""):
        _t, p = build_answer_with_provenance(
            "какова цена договора",
            hits,
            extractive_only=True,
        )
    assert cid in p
