"""PDF path for indexing: classification, optional Textract OCR, coverage metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.services.pdf_classification import needs_ocr, read_pdf_native_text_and_stats
from app.services.pdf_ocr_textract import (
    delete_s3_object,
    parse_s3_storage_key,
    run_textract_document_text_detection,
    upload_local_pdf_to_staging,
)
from app.services.text_extraction import ExtractedDocument, detect_language

logger = logging.getLogger(__name__)

CLASSIFICATION_VERSION = "1"


def _page_char_counts_from_merged(merged: str, page_count: int) -> list[int]:
    parts = merged.split("\f") if merged else []
    while len(parts) < page_count:
        parts.append("")
    counts: list[int] = []
    for i in range(page_count):
        raw = parts[i] if i < len(parts) else ""
        counts.append(len(" ".join((raw or "").split())))
    return counts


def _extraction_coverage_ratio(page_chars: list[int], min_chars: int) -> float:
    if not page_chars:
        return 0.0
    good = sum(1 for c in page_chars if c >= min_chars)
    return good / len(page_chars)


@dataclass(frozen=True)
class PdfIndexingExtractResult:
    extracted: ExtractedDocument
    pdf_kind: str | None
    ocr_applied: bool
    parser_version: str
    extraction_meta: dict


def extract_pdf_for_indexing(local_path: str, *, storage_key: str) -> PdfIndexingExtractResult:
    """
    Native pypdf extraction + optional AWS Textract when text is weak and OCR is enabled.

    ``storage_key`` is the document's storage key (``s3://...`` or local relative path).
    """
    merged, stats = read_pdf_native_text_and_stats(local_path)
    min_c = int(settings.pdf_min_chars_per_page)
    chars_before = stats.total_chars

    ocr_applied = False
    ocr_provider: str | None = None
    ocr_skip_reason: str | None = None
    textract_job_id: str | None = None
    final_text = merged
    native_page_count = stats.page_count

    ocr_configured = bool(settings.pdf_ocr_enabled) and settings.pdf_ocr_provider == "textract"
    weak = needs_ocr(stats)
    want_ocr = ocr_configured and weak

    if weak and not ocr_configured:
        ocr_skip_reason = "ocr_disabled_or_unconfigured"

    if want_ocr:
        bucket: str | None = None
        key: str | None = None
        staging_delete: tuple[str, str] | None = None
        parsed = parse_s3_storage_key(storage_key)
        if parsed:
            bucket, key = parsed
        else:
            try:
                bucket, key = upload_local_pdf_to_staging(local_path)
                staging_delete = (bucket, key)
            except Exception as e:
                ocr_skip_reason = "local_storage_no_staging"
                logger.info("OCR skipped (staging unavailable): %s", e)

        if bucket and key:
            try:
                ocr = run_textract_document_text_detection(bucket=bucket, key=key)
                ocr_applied = True
                ocr_provider = "textract"
                textract_job_id = ocr.job_id
                final_text = ocr.text
            except Exception as e:
                logger.warning("Textract OCR failed: %s", type(e).__name__)
                ocr_skip_reason = "textract_error"
                final_text = merged
            finally:
                if staging_delete:
                    delete_s3_object(staging_delete[0], staging_delete[1])
        else:
            final_text = merged

    if not final_text.strip():
        if weak and ocr_skip_reason == "local_storage_no_staging":
            raise ValueError(
                "Failed to extract text (empty). Configure pdf_ocr_staging_bucket for Textract when using local storage."
            )
        raise ValueError("Failed to extract text (empty)")

    pc_pages = native_page_count if native_page_count else 1
    if ocr_applied:
        parts = final_text.split("\f")
        pc_pages = max(len(parts), 1)

    effective_page_chars = _page_char_counts_from_merged(final_text, pc_pages)
    coverage = _extraction_coverage_ratio(effective_page_chars, min_c)

    meta = {
        "classification_version": CLASSIFICATION_VERSION,
        "pdf_kind": stats.pdf_kind,
        "chars_before_ocr": chars_before,
        "chars_after": len(final_text),
        "pypdf_mean_chars_per_page": stats.mean_chars_per_page,
        "pypdf_empty_page_ratio": stats.empty_page_ratio,
        "ocr_applied": ocr_applied,
        "ocr_provider": ocr_provider,
        "ocr_skip_reason": ocr_skip_reason,
        "textract_job_id": textract_job_id,
        "extraction_coverage": round(coverage, 4),
        "page_count_effective": pc_pages,
    }

    parser_version = "v2+textract" if ocr_applied else "v2"

    extracted = ExtractedDocument(
        text=final_text,
        page_count=pc_pages,
        language=detect_language(final_text),
    )
    return PdfIndexingExtractResult(
        extracted=extracted,
        pdf_kind=stats.pdf_kind,
        ocr_applied=ocr_applied,
        parser_version=parser_version,
        extraction_meta=meta,
    )
