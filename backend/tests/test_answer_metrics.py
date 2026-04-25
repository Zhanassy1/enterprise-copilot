"""Unit tests for deterministic answer quality metrics."""

from __future__ import annotations

import pytest

from app.eval.answer_eval_runner import load_answer_gold_jsonl
from app.eval.answer_metrics import (
    citation_chunk_precision,
    evidence_covers_required_chunk_ids,
    faithfulness_proxy_row,
    forbidden_satisfied,
    gold_chunks_in_top_k,
    grounded_line_ratio,
    line_grounded_in_hits,
    must_appear_satisfied,
    must_cover_satisfied,
    parse_citation_indices_from_answer,
    reference_token_f1,
)


def test_must_appear_satisfied() -> None:
    assert must_appear_satisfied("Цена 200 000 тенге", ["200 000"])
    assert not must_appear_satisfied("Цена договора", ["200 000"])
    assert must_appear_satisfied("x", [])


def test_gold_chunks_in_top_k() -> None:
    gold = {"a", "b"}
    ranked = ["x", "a", "b", "c"]
    assert gold_chunks_in_top_k(gold, ranked, k=3)
    assert not gold_chunks_in_top_k(gold, ranked, k=2)


def test_line_grounded_in_hits() -> None:
    hits = [{"text": "Неустойка за просрочку составляет 0,1% за каждый день."}]
    assert line_grounded_in_hits("Неустойка 0,1% за день просрочки", hits)
    assert not line_grounded_in_hits("Совершенно другой текст про космос", hits)


def test_load_answer_gold_jsonl(tmp_path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"query_id":"q1","query_text":"hello","gold_chunk_ids":["u1"],'
        '"must_appear_in_answer":["x"],"source_top_k":3,'
        '"must_cover":["m"],"forbidden_phrases":["z"],"reference_answer":"ref",'
        '"required_evidence_chunk_ids":["u1"]}\n',
        encoding="utf-8",
    )
    rows = load_answer_gold_jsonl(p)
    assert len(rows) == 1
    assert rows[0].query_id == "q1"
    assert rows[0].source_top_k == 3
    assert rows[0].must_appear_in_answer == ("x",)
    assert rows[0].must_cover == ("m",)
    assert rows[0].forbidden_phrases == ("z",)
    assert rows[0].reference_answer == "ref"
    assert "u1" in rows[0].required_evidence_chunk_ids


def test_grounded_line_ratio() -> None:
    hits = [{"text": "Alpha beta gamma."}, {"text": "Second chunk."}]
    ans = "Alpha beta\nirrelevant nonsense line here"
    r = grounded_line_ratio(ans, hits, min_chars=6)
    assert 0.0 <= r <= 1.0
    assert r == pytest.approx(0.5)


def test_must_cover_forbidden_ref_f1() -> None:
    assert must_cover_satisfied("A тенге B", ["тенге", "A"])
    assert not must_cover_satisfied("x", ["тенге"])
    assert forbidden_satisfied("ok", ["bad"])
    assert not forbidden_satisfied("bad phrase", ["bad ph"])
    assert reference_token_f1("a b c d", "a b c d") == pytest.approx(1.0)
    assert reference_token_f1("alphauniquexyz", "betauniquerst") < 0.1


def test_evidence_covers_required() -> None:
    u1 = "f0000001-0001-0001-0001-000000000001"
    import uuid

    a = uuid.UUID(u1)
    assert evidence_covers_required_chunk_ids([a], {u1})
    assert not evidence_covers_required_chunk_ids([], {u1})


def test_parse_citation_indices() -> None:
    assert parse_citation_indices_from_answer("See [1] and [2]") == {1, 2}


def test_citation_chunk_precision() -> None:
    u1 = "f0000001-0001-0001-0001-000000000001"
    u2 = "f0000001-0001-0001-0001-000000000002"
    gr = {u1, u2}
    assert citation_chunk_precision([], gold_relevant=gr) == 0.0
    assert citation_chunk_precision([u1, u1], gold_relevant=gr) == 1.0
    assert citation_chunk_precision([u1, u2], gold_relevant=gr) == 1.0
    import uuid

    assert citation_chunk_precision([uuid.UUID(u1), u2], gold_relevant=gr) == 1.0
    u3 = "f0000001-0001-0001-0001-000000000099"
    assert abs(citation_chunk_precision([u1, u2, u3], gold_relevant=gr) - (2.0 / 3.0)) < 0.0001
    assert citation_chunk_precision([u1], gold_relevant=set()) == 1.0


def test_faithfulness_proxy_row() -> None:
    p = faithfulness_proxy_row(0.8, evidence_ok=True, forbidden_ok=True, has_required_evidence=False, reference_f1=None)
    assert p == pytest.approx(0.9)
    p2 = faithfulness_proxy_row(1.0, evidence_ok=False, forbidden_ok=True, has_required_evidence=True, reference_f1=0.5)
    assert p2 == pytest.approx(0.625)
    assert not parse_citation_indices_from_answer("no brackets")
