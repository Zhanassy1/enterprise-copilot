"""Extract auxiliary search tokens for procurement / SKU / mixed-language chunks."""

from __future__ import annotations

import re

# Alphanumeric + Cyrillic/Latin run with internal -/. (part numbers, GOST refs, etc.)
_CODE_TOKEN_RE = re.compile(
    r"[A-Za-zА-Яа-яЁё0-9](?:[A-Za-zА-Яа-яЁё0-9\-/.]*[A-Za-zА-Яа-яЁё0-9])?",
    re.UNICODE,
)
_APPENDIX_RE = re.compile(
    r"приложение\s*(?:№|N|n\.?)\s*[\w\-.]+",
    re.IGNORECASE | re.UNICODE,
)

_MAX_AUX_CHARS = 12_000


def build_chunk_search_aux(text: str) -> str:
    """
    Space-separated unique tokens for ``simple`` FTS on ``chunk_search_aux``.
    Keeps part-style tokens and appendix references without replacing main RU/simple vectors.
    """
    if not text:
        return ""
    seen: set[str] = set()
    parts: list[str] = []

    def add(raw: str) -> None:
        t = raw.strip()
        if len(t) < 2:
            return
        key = t.casefold()
        if key in seen:
            return
        seen.add(key)
        parts.append(t)

    for m in _CODE_TOKEN_RE.finditer(text):
        add(m.group(0))
    for m in _APPENDIX_RE.finditer(text):
        add(m.group(0).replace("\n", " ").strip())

    out = " ".join(parts)
    if len(out) > _MAX_AUX_CHARS:
        return out[:_MAX_AUX_CHARS]
    return out
