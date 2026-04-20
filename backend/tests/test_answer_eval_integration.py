"""Integration: answer_gold.jsonl + seed corpus (Postgres + pgvector)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.eval.answer_eval_runner import load_answer_gold_jsonl, run_answer_quality_eval
from app.eval.seed_corpus import seed_retrieval_eval_corpus

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_ANSWER_GOLD = BACKEND_ROOT / "eval" / "answer_gold.jsonl"

pytestmark = [
    pytest.mark.retrieval_regression,
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION_TESTS") != "1",
        reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
    ),
]


def test_answer_quality_eval_on_seed_corpus() -> None:
    gold_rows = load_answer_gold_jsonl(_ANSWER_GOLD)
    db = SessionLocal()
    try:
        ws_id, uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        metrics = run_answer_quality_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            reranker_enabled=False,
        )
    finally:
        db.close()

    assert metrics["source_gold_all_in_top_k_rate"] >= 0.99
    assert metrics["must_appear_rate"] >= 0.99
    assert metrics["mean_grounded_line_ratio"] >= 0.85
