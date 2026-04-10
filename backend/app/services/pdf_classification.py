"""Heuristic classification of PDFs: native text vs scanned / mixed."""

from __future__ import annotations

from dataclasses import dataclass

import pypdf

from app.constants.pdf_ingestion import PDF_KIND_MIXED, PDF_KIND_SCANNED, PDF_KIND_TEXT_NATIVE
from app.core.config import settings


def _normalize_page_text(raw: str | None) -> str:
    return " ".join((raw or "").split())


@dataclass(frozen=True)
class PdfPageTextStats:
    page_chars: list[int]
    total_chars: int
    page_count: int
    empty_pages: int
    mean_chars_per_page: float
    empty_page_ratio: float
    pdf_kind: str
    sufficient_native_text: bool


def classify_pdf_pages(page_chars: list[int], *, min_chars_per_page: int, min_mean: int, max_empty_ratio: float) -> PdfPageTextStats:
    n = len(page_chars)
    if n == 0:
        return PdfPageTextStats(
            page_chars=[],
            total_chars=0,
            page_count=0,
            empty_pages=0,
            mean_chars_per_page=0.0,
            empty_page_ratio=0.0,
            pdf_kind=PDF_KIND_SCANNED,
            sufficient_native_text=False,
        )

    total = sum(page_chars)
    empty_pages = sum(1 for c in page_chars if c < min_chars_per_page)
    mean = total / n
    er = empty_pages / n
    sufficient = mean >= float(min_mean) and er <= max_empty_ratio

    if sufficient:
        kind = PDF_KIND_TEXT_NATIVE
    elif er >= 0.9 or mean < 5.0:
        kind = PDF_KIND_SCANNED
    else:
        kind = PDF_KIND_MIXED

    return PdfPageTextStats(
        page_chars=page_chars,
        total_chars=total,
        page_count=n,
        empty_pages=empty_pages,
        mean_chars_per_page=mean,
        empty_page_ratio=er,
        pdf_kind=kind,
        sufficient_native_text=sufficient,
    )


def needs_ocr(stats: PdfPageTextStats) -> bool:
    """True when native extraction is too weak for RAG without OCR."""
    return not stats.sufficient_native_text


def read_pdf_native_text_and_stats(
    path: str,
    *,
    min_chars_per_page: int | None = None,
    min_mean: int | None = None,
    max_empty_ratio: float | None = None,
) -> tuple[str, PdfPageTextStats]:
    """Single pypdf pass: merged text (pages joined with ``\\f``) + classification stats."""
    reader = pypdf.PdfReader(path)
    texts: list[str] = []
    page_chars: list[int] = []
    for page in reader.pages:
        raw = page.extract_text() or ""
        texts.append(raw)
        page_chars.append(len(_normalize_page_text(raw)))
    stats = classify_pdf_pages(
        page_chars,
        min_chars_per_page=int(min_chars_per_page if min_chars_per_page is not None else settings.pdf_min_chars_per_page),
        min_mean=int(min_mean if min_mean is not None else settings.pdf_min_mean_chars_per_page),
        max_empty_ratio=float(max_empty_ratio if max_empty_ratio is not None else settings.pdf_max_empty_page_ratio),
    )
    merged = "\n\f\n".join(texts).strip()
    return merged, stats
