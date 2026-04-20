"""Golden expectations for real ``chunk_text`` (ingestion regression)."""

from __future__ import annotations

from pathlib import Path

from app.services.chunking import chunk_text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = BACKEND_ROOT / "eval" / "fixtures" / "chunking_golden.txt"


def test_chunking_golden_fixture_paragraph_boundaries() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").strip()
    # Deterministic: two paragraphs fit first buffer, third flushes — expect >=2 chunks.
    chunks = chunk_text(text, chunk_size=400, overlap=0)
    assert len(chunks) >= 2
    joined = "\n".join(chunks)
    assert "MARK_BLOCK_A" in joined
    assert "MARK_BLOCK_B" in joined
    assert "MARK_BLOCK_C" in joined
    assert chunks[0].startswith("MARK_BLOCK_A") or "MARK_BLOCK_A" in chunks[0]
    assert any("MARK_BLOCK_B" in c for c in chunks)
    assert any("MARK_BLOCK_C" in c for c in chunks)


def test_chunking_overlap_preserves_markers() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").strip()
    chunks = chunk_text(text, chunk_size=350, overlap=80)
    assert len(chunks) >= 2
    joined = "\n".join(chunks)
    for marker in ("MARK_BLOCK_A", "MARK_BLOCK_B", "MARK_BLOCK_C"):
        assert marker in joined, f"missing {marker} after overlap chunking"
