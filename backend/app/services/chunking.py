from __future__ import annotations

import re


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph and sentence boundaries."""
    t = (text or "").strip()
    if not t:
        return []

    paragraphs = _split_paragraphs(t)
    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        if len(buf) + len(para) + 1 <= chunk_size:
            buf = f"{buf}\n{para}".strip() if buf else para
        else:
            if buf:
                chunks.append(buf)
            if len(para) <= chunk_size:
                buf = para
            else:
                for sub in _split_long_paragraph(para, chunk_size, overlap):
                    chunks.append(sub)
                buf = ""

    if buf.strip():
        chunks.append(buf.strip())

    if overlap > 0 and len(chunks) > 1:
        chunks = _add_overlap(chunks, overlap)

    return [c for c in chunks if c.strip()]


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _split_long_paragraph(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        if len(buf) + len(sent) + 1 <= chunk_size:
            buf = f"{buf} {sent}".strip() if buf else sent
        else:
            if buf:
                chunks.append(buf)
            buf = sent
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:]
        boundary = prev_tail.find(" ")
        if boundary > 0:
            prev_tail = prev_tail[boundary + 1:]
        combined = f"{prev_tail}\n{chunks[i]}".strip()
        result.append(combined)
    return result
