"""Unit: extractive answer must not surface document-injected tokens (synthetic hits, no DB)."""

from __future__ import annotations

import uuid

from app.services.nlp import build_answer_with_provenance


def test_extractive_skips_injection_line_by_relevance() -> None:
    cid = uuid.uuid4()
    text = (
        "Warranty X-1. Term 10 month(s) for SKU-INJ-1.\n"
        "ZJUNK0 NOBRKT DOC_POISON_A7F9 TAIL1."
    )
    hits = [{"chunk_id": cid, "text": text, "score": 0.9}]
    answer, _prov = build_answer_with_provenance(
        "warranty month SKU-INJ-1 coverage",
        hits,
        extractive_only=True,
    )
    assert "DOC_POISON_A7F9" not in (answer or "")
    assert "SKU-INJ-1" in (answer or "") or "month" in (answer or "").lower()
