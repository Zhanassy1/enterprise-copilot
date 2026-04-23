"""Normalize user search text before embedding, hybrid keyword SQL, and reranking."""

from __future__ import annotations

import re
import unicodedata

# Zero-width and BOM; removed so tsquery/embedding do not get invisible tokens.
_ZW_BOM = frozenset({"\u200b", "\u200c", "\u200d", "\ufeff"})

_WS_COLLAPSE = re.compile(r"[^\S\n\r]+", re.UNICODE)

_C0_BREAK = frozenset("\t\n\r\v\f")


def _map_controls_to_space(s: str) -> str:
    out: list[str] = []
    for c in s:
        o = ord(c)
        if c == "\x00" or c in _ZW_BOM:
            continue
        if c in _C0_BREAK:
            out.append(" ")
        elif 0x20 <= o < 0x7F:  # printable ASCII
            out.append(c)
        elif o < 0x20:
            continue  # other C0
        elif o == 0x7F:  # DEL
            continue
        elif 0x80 <= o <= 0x9F:  # C1
            continue
        else:
            out.append(c)
    return "".join(out)


def normalize_search_query_for_retrieval(s: str) -> str:
    """
    NFC, strip C0 (except line/tab to space), drop ZWSP/BOM, drop C1, collapse whitespace.
    If that yields empty but stripped input was non-empty, return a lighter strip
    (NUL + ZW* removed) or NFC of the original.
    """
    raw = (s or "").strip()
    if not raw:
        return raw

    nfc = unicodedata.normalize("NFC", raw)
    cleaned = _map_controls_to_space(nfc)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = _WS_COLLAPSE.sub(" ", cleaned)
    combined = " ".join(cleaned.split())
    if combined:
        return combined

    light = nfc.replace("\x00", "")
    for z in _ZW_BOM:
        light = light.replace(z, "")
    light = " ".join(light.split())
    if light:
        return light
    return nfc
