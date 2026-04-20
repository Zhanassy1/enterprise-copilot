"""Unit tests for deterministic answer quality metrics."""

from __future__ import annotations

import pytest

from app.eval.answer_eval_runner import load_answer_gold_jsonl
from app.eval.answer_metrics import (
    gold_chunks_in_top_k,
    grounded_line_ratio,
    line_grounded_in_hits,
    must_appear_satisfied,
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
        '"must_appear_in_answer":["x"],"source_top_k":3}\n',
        encoding="utf-8",
    )
    rows = load_answer_gold_jsonl(p)
    assert len(rows) == 1
    assert rows[0].query_id == "q1"
    assert rows[0].source_top_k == 3
    assert rows[0].must_appear_in_answer == ("x",)


def test_grounded_line_ratio() -> None:
    hits = [{"text": "Alpha beta gamma."}, {"text": "Second chunk."}]
    ans = "Alpha beta\nirrelevant nonsense line here"
    r = grounded_line_ratio(ans, hits, min_chars=6)
    assert 0.0 <= r <= 1.0
    assert r == pytest.approx(0.5)
