"""Rerank paired eval: delta report (unit) and wiring vs stub (integration)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.eval.eval_config import load_retrieval_eval_config, resolve_backend_paths
from app.eval.retrieval_eval_runner import (
    build_rerank_gain_report,
    load_gold_jsonl,
    run_rerank_gain_eval,
    run_retrieve_ranked_hits_eval,
)
from app.eval.seed_corpus import seed_retrieval_eval_corpus

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_EVAL_CONFIG_PATH = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"


def test_build_rerank_gain_report_deltas() -> None:
    off = {"mrr": 0.5, "recall_at_5": 0.8}
    on = {"mrr": 0.75, "recall_at_5": 0.9}
    rep = build_rerank_gain_report(off, on)
    assert rep["delta"]["mrr"] == pytest.approx(0.25)
    assert rep["delta"]["recall_at_5"] == pytest.approx(0.1)
    assert rep["reranker_disabled"]["mrr"] == 0.5


@pytest.mark.retrieval_regression
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
)
def test_rerank_gain_stub_identity_matches_baseline_path() -> None:
    """With rerank_hits stubbed to identity, on/off ranked metrics should match (wiring + quota path)."""
    cfg = load_retrieval_eval_config(_EVAL_CONFIG_PATH)
    gold_path, _ = resolve_backend_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gold_path)

    db = SessionLocal()
    try:
        ws_id, uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        with patch("app.services.rag_retrieval.rerank_hits", side_effect=lambda q, h, top_n: h):
            rep = run_rerank_gain_eval(
                db,
                workspace_id=ws_id,
                user_id=uid,
                gold_rows=gold_rows,
                k_list=cfg.k_list,
            )
    finally:
        db.close()

    off = rep["reranker_disabled"]
    on = rep["reranker_enabled"]
    assert off["mrr"] == pytest.approx(on["mrr"])
    assert off["recall_at_5"] == pytest.approx(on["recall_at_5"])
    assert abs(float(rep["delta"]["mrr"])) < 1e-9


@pytest.mark.retrieval_regression
@pytest.mark.rerank_gain
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
)
@pytest.mark.skipif(
    os.environ.get("RUN_RERANK_EVAL") != "1",
    reason="Optional: set RUN_RERANK_EVAL=1 to run real cross-encoder paired eval (slow, downloads weights).",
)
def test_rerank_gain_real_cross_encoder_paired() -> None:
    """Real rerank on vs off; no strict baseline — smoke that report is well-formed."""
    cfg = load_retrieval_eval_config(_EVAL_CONFIG_PATH)
    gold_path, _ = resolve_backend_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gold_path)

    db = SessionLocal()
    try:
        ws_id, uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        rep = run_rerank_gain_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            k_list=cfg.k_list,
        )
    finally:
        db.close()

    assert "reranker_disabled" in rep
    assert "reranker_enabled" in rep
    assert "delta" in rep
    assert float(rep["reranker_disabled"]["mrr"]) >= 0.0


@pytest.mark.retrieval_regression
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL + pgvector).",
)
def test_retrieve_ranked_hits_eval_rerank_flag_backward_compat() -> None:
    cfg = load_retrieval_eval_config(_EVAL_CONFIG_PATH)
    gold_path, _ = resolve_backend_paths(BACKEND_ROOT, cfg)
    gold_rows = load_gold_jsonl(gold_path)

    db = SessionLocal()
    try:
        ws_id, uid, _did = seed_retrieval_eval_corpus(db)
        db.commit()
        default_off = run_retrieve_ranked_hits_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            k_list=cfg.k_list,
        )
        explicit_off = run_retrieve_ranked_hits_eval(
            db,
            workspace_id=ws_id,
            user_id=uid,
            gold_rows=gold_rows,
            k_list=cfg.k_list,
            reranker_enabled=False,
        )
    finally:
        db.close()

    assert default_off["mrr"] == pytest.approx(explicit_off["mrr"])
