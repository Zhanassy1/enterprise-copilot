"""Unit tests for retrieval eval config loader."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.eval_config import (
    load_retrieval_eval_config,
    resolve_backend_paths,
    resolve_ranked_baseline_path,
)


def test_ranked_baseline_optional(tmp_path: Path) -> None:
    p = tmp_path / "minimal.json"
    p.write_text(
        json.dumps(
            {
                "gold_relative": "eval/a.jsonl",
                "baseline_relative": "eval/b.json",
                "k_list": [1, 10],
                "regression_epsilon": 0.01,
            }
        ),
        encoding="utf-8",
    )
    c = load_retrieval_eval_config(p)
    assert c.ranked_baseline_relative is None
    assert resolve_ranked_baseline_path(tmp_path, c) is None


def test_load_retrieval_eval_config_defaults(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "gold_relative": "eval/a.jsonl",
                "baseline_relative": "eval/b.json",
                "k_list": [1, 5],
                "regression_epsilon": 0.03,
            }
        ),
        encoding="utf-8",
    )
    c = load_retrieval_eval_config(p)
    assert c.gold_relative == "eval/a.jsonl"
    assert c.k_list == (1, 5)
    assert c.regression_epsilon == 0.03


def test_resolve_backend_paths() -> None:
    c = load_retrieval_eval_config(
        Path(__file__).resolve().parents[1] / "eval" / "retrieval_eval.config.json"
    )
    root = Path(__file__).resolve().parents[1]
    g, b = resolve_backend_paths(root, c)
    assert g.name == "retrieval_gold.jsonl"
    assert b.name == "baseline_metrics.json"
    assert c.ranked_baseline_relative == "eval/baseline_metrics_ranked.json"
    rb = resolve_ranked_baseline_path(root, c)
    assert rb is not None
    assert rb.name == "baseline_metrics_ranked.json"
