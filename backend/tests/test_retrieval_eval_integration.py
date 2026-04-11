"""Integration: seeded corpus + gold JSONL + baseline regression gate (PostgreSQL + pgvector)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.eval.eval_config import (
    RetrievalEvalConfig,
    load_retrieval_eval_config,
    resolve_backend_paths,
    resolve_ranked_baseline_path,
)
from app.eval.retrieval_eval_runner import (
    compare_to_baseline,
    load_baseline_metrics,
    load_gold_jsonl,
    run_retrieve_ranked_hits_eval,
    run_search_chunks_eval,
)
from app.eval.seed_corpus import seed_retrieval_eval_corpus

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_EVAL_CONFIG_PATH = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"

pytestmark = [
    pytest.mark.retrieval_regression,
    pytest.mark.skipif(
        os.environ.get("RUN_INTEGRATION_TESTS") != "1",
        reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
    ),
]


def _load_cfg() -> RetrievalEvalConfig:
    return load_retrieval_eval_config(_EVAL_CONFIG_PATH)


def test_retrieval_eval_regression_gate() -> None:
    """Vector-stage metrics must stay at or above committed baseline (with epsilon)."""
    cfg = _load_cfg()
    gold_path, baseline_path = resolve_backend_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gold_path)
    baseline = load_baseline_metrics(baseline_path)

    db = SessionLocal()
    try:
        ws_id, _uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        metrics = run_search_chunks_eval(
            db, workspace_id=ws_id, gold_rows=gold_rows, k_list=cfg.k_list
        )
    finally:
        db.close()

    ok, failures = compare_to_baseline(metrics, baseline, epsilon=cfg.regression_epsilon)
    assert ok, failures


def test_retrieval_ranked_hits_regression_gate() -> None:
    """Full RAG path (rerank off): compaction + contract-value rules vs ranked baseline."""
    cfg = _load_cfg()
    ranked_path = resolve_ranked_baseline_path(BACKEND_ROOT, cfg)
    assert ranked_path is not None, "ranked_baseline_relative must be set in retrieval_eval.config.json"

    gold_path, _ = resolve_backend_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gold_path)
    baseline = load_baseline_metrics(ranked_path)

    db = SessionLocal()
    try:
        ws_id, uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        metrics = run_retrieve_ranked_hits_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            k_list=cfg.k_list,
        )
    finally:
        db.close()

    ok, failures = compare_to_baseline(metrics, baseline, epsilon=cfg.regression_epsilon)
    assert ok, failures


def test_baseline_file_matches_schema() -> None:
    cfg = _load_cfg()
    _, baseline_path = resolve_backend_paths(BACKEND_ROOT, cfg)
    raw = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    assert "mrr" in raw
    assert "recall_at_5" in raw
    assert "ndcg_at_5" in raw


@pytest.mark.skipif(
    os.environ.get("RUN_RETRIEVAL_SMOKE") != "1",
    reason="Optional: set RUN_RETRIEVAL_SMOKE=1 for fast smoke gold (one query).",
)
def test_retrieval_eval_smoke_sanity() -> None:
    """Single-row gold: pipeline runs and finds the labeled chunk (no separate baseline file)."""
    cfg = _load_cfg()
    gold_path = BACKEND_ROOT / "eval" / "retrieval_gold_smoke.jsonl"
    gold_rows = load_gold_jsonl(gold_path)

    db = SessionLocal()
    try:
        ws_id, _uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        metrics = run_search_chunks_eval(
            db, workspace_id=ws_id, gold_rows=gold_rows, k_list=cfg.k_list
        )
    finally:
        db.close()

    assert metrics["mrr"] >= 0.99
    assert metrics["recall_at_5"] >= 0.99
