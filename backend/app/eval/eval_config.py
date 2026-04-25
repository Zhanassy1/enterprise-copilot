"""Load retrieval offline-eval config (paths, k-list, regression epsilon)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RetrievalEvalConfig:
    """Parameters for ``scripts/eval_retrieval.py`` and CI-style regression checks."""

    gold_relative: str
    baseline_relative: str
    k_list: tuple[int, ...]
    regression_epsilon: float
    notes: str = ""
    ranked_baseline_relative: str | None = None
    answer_gold_relative: str = "eval/answer_gold.jsonl"
    # P2 (large synthetic gold, multilingual + safety fixtures)
    gold_p2_relative: str = "eval/retrieval_gold_p2.jsonl"
    answer_gold_p2_relative: str = "eval/answer_gold_p2.jsonl"
    baseline_p2_retrieval_relative: str = "eval/baseline_metrics_p2.json"
    baseline_p2_answer_relative: str = "eval/baseline_p2_answer.json"
    p2_regression_epsilon: float = 0.12

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RetrievalEvalConfig:
        k_raw = raw.get("k_list") or [1, 3, 5, 10]
        k_list = tuple(int(x) for x in k_raw)
        rb = raw.get("ranked_baseline_relative")
        ag = raw.get("answer_gold_relative") or "eval/answer_gold.jsonl"
        return cls(
            gold_relative=str(raw["gold_relative"]),
            baseline_relative=str(raw["baseline_relative"]),
            k_list=k_list,
            regression_epsilon=float(raw.get("regression_epsilon", 0.02)),
            notes=str(raw.get("notes") or ""),
            ranked_baseline_relative=str(rb) if rb else None,
            answer_gold_relative=str(ag),
            gold_p2_relative=str(raw.get("gold_p2_relative") or "eval/retrieval_gold_p2.jsonl"),
            answer_gold_p2_relative=str(raw.get("answer_gold_p2_relative") or "eval/answer_gold_p2.jsonl"),
            baseline_p2_retrieval_relative=str(
                raw.get("baseline_p2_retrieval_relative") or "eval/baseline_metrics_p2.json"
            ),
            baseline_p2_answer_relative=str(
                raw.get("baseline_p2_answer_relative") or "eval/baseline_p2_answer.json"
            ),
            p2_regression_epsilon=float(raw.get("p2_regression_epsilon", 0.12)),
        )


def load_retrieval_eval_config(path: Path) -> RetrievalEvalConfig:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return RetrievalEvalConfig.from_dict(data)


def resolve_backend_paths(
    backend_root: Path,
    config: RetrievalEvalConfig,
) -> tuple[Path, Path]:
    """Absolute paths to gold JSONL and baseline JSON."""
    gold = (backend_root / config.gold_relative).resolve()
    baseline = (backend_root / config.baseline_relative).resolve()
    return gold, baseline


def resolve_ranked_baseline_path(
    backend_root: Path,
    config: RetrievalEvalConfig,
) -> Path | None:
    """Absolute path to ranked-pipeline baseline JSON, if configured."""
    if not config.ranked_baseline_relative:
        return None
    return (backend_root / config.ranked_baseline_relative).resolve()


def resolve_answer_gold_path(backend_root: Path, config: RetrievalEvalConfig) -> Path:
    """Absolute path to answer + citation gold JSONL."""
    return (backend_root / config.answer_gold_relative).resolve()


def resolve_p2_gold_paths(
    backend_root: Path, config: RetrievalEvalConfig
) -> tuple[Path, Path, Path, Path]:
    """retrieval p2, answer p2, baseline retrieval, baseline answer (absolute)."""
    return (
        (backend_root / config.gold_p2_relative).resolve(),
        (backend_root / config.answer_gold_p2_relative).resolve(),
        (backend_root / config.baseline_p2_retrieval_relative).resolve(),
        (backend_root / config.baseline_p2_answer_relative).resolve(),
    )
