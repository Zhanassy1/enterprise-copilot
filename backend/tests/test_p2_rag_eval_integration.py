"""P2: 50-row synthetic gold, multilingual + injection; regression when RUN_P2_EVAL=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.eval.answer_eval_runner import load_answer_gold_jsonl, run_answer_quality_eval
from app.eval.eval_config import load_retrieval_eval_config, resolve_p2_gold_paths
from app.eval.retrieval_eval_runner import (
    compare_to_baseline,
    load_baseline_metrics,
    load_gold_jsonl,
    run_retrieve_ranked_hits_eval,
)
from app.eval.seed_corpus import seed_p2_rag_eval_corpus

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_EVAL_CONFIG = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"

pytestmark = [
    pytest.mark.p2_rag,
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION_TESTS") != "1",
        reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
    ),
    pytest.mark.skipif(
        os.environ.get("RUN_P2_EVAL") != "1",
        reason="Set RUN_P2_EVAL=1 to run 50-row P2 eval (slower, larger seed).",
    ),
]


def test_p2_answer_metrics_regression_gate() -> None:
    cfg = load_retrieval_eval_config(_EVAL_CONFIG)
    _, ap, _, blp = resolve_p2_gold_paths(BACKEND_ROOT, cfg)
    rows = load_answer_gold_jsonl(ap)
    baseline = load_baseline_metrics(blp)

    db = SessionLocal()
    try:
        ws_id, uid, _ = seed_p2_rag_eval_corpus(db)
        db.commit()
        metrics = run_answer_quality_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=rows,
            reranker_enabled=False,
            k_list=cfg.k_list,
        )
    finally:
        db.close()

    ok, failures = compare_to_baseline(
        metrics, baseline, epsilon=cfg.p2_regression_epsilon
    )
    assert ok, failures


def test_p2_retrieve_ranked_hits_regression_gate() -> None:
    """Ranked full path (rerank off) on P2 retrieval gold — separate baseline file."""
    cfg = load_retrieval_eval_config(_EVAL_CONFIG)
    gp, _, br, _ = resolve_p2_gold_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gp)
    baseline = load_baseline_metrics(br)

    db = SessionLocal()
    try:
        ws_id, uid, _ = seed_p2_rag_eval_corpus(db)
        db.commit()
        metrics = run_retrieve_ranked_hits_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            k_list=cfg.k_list,
            reranker_enabled=False,
        )
    finally:
        db.close()

    ok, failures = compare_to_baseline(
        metrics, baseline, epsilon=cfg.p2_regression_epsilon
    )
    assert ok, failures
