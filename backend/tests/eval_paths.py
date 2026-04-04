"""Resolve repo ``docs/evals`` files when tests run from ``backend/tests`` or Docker ``/app/tests``."""

from __future__ import annotations

from pathlib import Path


def find_evals_file(name: str) -> Path | None:
    """Walk parents until ``docs/evals/<name>`` exists (monorepo root)."""
    start = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = start / "docs" / "evals" / name
        if candidate.is_file():
            return candidate
        parent = start.parent
        if parent == start:
            break
        start = parent
    return None
