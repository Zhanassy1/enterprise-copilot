"""Integration: seeded corpus + gold JSONL + baseline regression gate (PostgreSQL + pgvector)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.eval.retrieval_eval_runner import (
    compare_to_baseline,
    default_eval_paths,
    load_baseline_metrics,
    load_gold_jsonl,
    run_search_chunks_eval,
)
from app.eval.seed_corpus import seed_retrieval_eval_corpus

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
)


def test_retrieval_eval_regression_gate() -> None:
    """End-to-end metrics must stay at or above committed baseline (with epsilon)."""
    gold_path, baseline_path = default_eval_paths()
    gold_rows = load_gold_jsonl(gold_path)
    baseline = load_baseline_metrics(baseline_path)

    db = SessionLocal()
    try:
        ws_id, _uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        metrics = run_search_chunks_eval(db, workspace_id=ws_id, gold_rows=gold_rows)
    finally:
        db.close()

    ok, failures = compare_to_baseline(metrics, baseline, epsilon=0.02)
    assert ok, failures


def test_baseline_file_matches_schema() -> None:
    _, baseline_path = default_eval_paths()
    raw = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    assert "mrr" in raw
    assert "recall_at_5" in raw
    assert "ndcg_at_5" in raw
