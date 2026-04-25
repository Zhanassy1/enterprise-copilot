#!/usr/bin/env python3
"""
Grid / random search over retrieval settings using train/holdout split on gold query_id.

Usage (from ``backend/``, DB ready, same as eval_retrieval)::

  set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
  python scripts/tune_retrieval.py --gold eval/retrieval_gold.jsonl
  python scripts/tune_retrieval.py --random 20 --seed 42

Does not write baselines; prints JSON with best params and metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from itertools import product
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.eval.retrieval_eval_harness import retrieval_overrides_from_mapping  # noqa: E402
from app.eval.retrieval_eval_runner import (  # noqa: E402
    GoldRow,
    load_gold_jsonl,
    run_search_chunks_eval,
)


def _split_train_holdout(
    rows: list[GoldRow],
    *,
    train_fraction: float,
    rng: random.Random,
) -> tuple[list[GoldRow], list[GoldRow]]:
    ids = list(rows)
    rng.shuffle(ids)
    n_train = max(1, int(len(ids) * train_fraction))
    if n_train >= len(ids):
        n_train = len(ids) - 1 if len(ids) > 1 else 1
    train = ids[:n_train]
    holdout = ids[n_train:]
    if not holdout:
        holdout = [train.pop()]
    return train, holdout


def _objective(metrics: dict[str, float], objective: str) -> float:
    if objective in metrics:
        return float(metrics[objective])
    if objective == "mrr":
        return float(metrics.get("mrr", 0.0))
    return float(metrics.get("ndcg_at_10", metrics.get("mrr", 0.0)))


def _default_grid() -> list[dict[str, float | int]]:
    rrf_k = (40, 60, 80)
    wd = (0.8, 1.0, 1.2)
    wk = (0.8, 1.0, 1.2)
    mult = (8, 10, 12)
    floor = (40, 60, 80)
    out: list[dict[str, float | int]] = []
    for rk, d, k, m, f in product(rrf_k, wd, wk, mult, floor):
        out.append(
            {
                "retrieval_rrf_k": rk,
                "retrieval_rrf_weight_dense": d,
                "retrieval_rrf_weight_keyword": k,
                "retrieval_candidate_multiplier": m,
                "retrieval_candidate_floor": f,
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Train/holdout grid search for retrieval settings.")
    parser.add_argument("--gold", type=Path, default=BACKEND_ROOT / "eval" / "retrieval_gold.jsonl")
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--objective", type=str, default="mrr", help="Metric key from aggregate_metrics*")
    parser.add_argument("--random", type=int, default=0, help="Sample this many configs from full grid (0=full grid)")
    parser.add_argument("--max-combos", type=int, default=200, help="Cap grid size when using full grid")
    args = parser.parse_args()

    ws = os.environ.get("RETRIEVAL_EVAL_WORKSPACE_ID", "").strip()
    if not ws:
        print("Set RETRIEVAL_EVAL_WORKSPACE_ID", file=sys.stderr)
        return 1
    workspace_id = UUID(ws)

    gold_path = args.gold.resolve()
    gold_rows = load_gold_jsonl(gold_path)
    if len(gold_rows) < 2:
        print("Need at least 2 gold rows for train/holdout split.", file=sys.stderr)
        return 1

    rng = random.Random(int(args.seed))
    train, holdout = _split_train_holdout(
        gold_rows, train_fraction=float(args.train_fraction), rng=rng
    )

    grid = _default_grid()
    if int(args.random) > 0:
        rng.shuffle(grid)
        grid = grid[: int(args.random)]
    elif len(grid) > int(args.max_combos):
        rng.shuffle(grid)
        grid = grid[: int(args.max_combos)]

    k_list = (1, 3, 5, 10)
    db = SessionLocal()
    best: tuple[float, dict[str, float | int], dict[str, float], dict[str, float]] | None = None
    try:
        for combo in grid:
            ovr = retrieval_overrides_from_mapping(combo)
            train_metrics = run_search_chunks_eval(
                db,
                workspace_id=workspace_id,
                gold_rows=train,
                k_list=k_list,
                settings_overrides=ovr,
            )
            score = _objective(train_metrics, args.objective)
            if best is None or score > best[0]:
                hold_metrics = run_search_chunks_eval(
                    db,
                    workspace_id=workspace_id,
                    gold_rows=holdout,
                    k_list=k_list,
                    settings_overrides=ovr,
                )
                best = (score, combo, train_metrics, hold_metrics)
    finally:
        db.close()

    if not best:
        return 1
    out = {
        "best_train_objective": best[0],
        "objective_key": args.objective,
        "best_params": best[1],
        "train_metrics": best[2],
        "holdout_metrics": best[3],
        "train_query_ids": [r.query_id for r in train],
        "holdout_query_ids": [r.query_id for r in holdout],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
