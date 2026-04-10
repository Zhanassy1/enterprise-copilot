# PDF ingestion: native text, classification, Textract OCR

## Flow

1. **pypdf** extracts text per page; pages are joined with a form feed (`\f`) so chunk → page mapping stays consistent with `document_indexing._page_spans`.
2. **Heuristic classification** (`pdf_kind`: `text_native` | `scanned` | `mixed`) uses per-page character counts, mean characters per page, and the ratio of “trivially empty” pages (below `PDF_MIN_CHARS_PER_PAGE`). Thresholds: `PDF_MIN_MEAN_CHARS_PER_PAGE`, `PDF_MAX_EMPTY_PAGE_RATIO` (see `IngestionSettings`).
3. If native text is **sufficient**, indexing uses it and `parser_version` is **`v2`** (no OCR).
4. If native text is **weak** and **`PDF_OCR_ENABLED=1`** with **`PDF_OCR_PROVIDER=textract`**, the worker calls **AWS Textract** `StartDocumentTextDetection` on the object in S3, polls until completion, merges LINE blocks by page, and indexes that text. Then `parser_version` is **`v2+textract`** and `ocr_applied` is true.

## Extraction coverage

`extraction_meta.extraction_coverage` is the fraction of pages that have at least `PDF_MIN_CHARS_PER_PAGE` non-whitespace characters **after** the final extraction step (native or OCR). It is stored in JSON on `documents.extraction_meta` and surfaced on the API as `extraction_coverage` (derived).

## Storage requirements for Textract

- **S3 storage:** `storage_key` is `s3://bucket/key`; Textract reads that object directly (same bucket as uploads; IAM must allow `s3:GetObject` and Textract actions).
- **Local file storage:** Textract cannot read local disk. Set **`PDF_OCR_STAGING_BUCKET`** (and optionally `PDF_OCR_STAGING_PREFIX`) so the worker uploads a temporary copy to S3, runs Textract, then deletes the staging object. Without staging, weak native text on local storage fails with a clear error when text would otherwise be empty.

## Environment (see `backend/.env.example`)

- `PDF_OCR_ENABLED`, `PDF_OCR_PROVIDER` (`none` | `textract`)
- Classification: `PDF_MIN_CHARS_PER_PAGE`, `PDF_MIN_MEAN_CHARS_PER_PAGE`, `PDF_MAX_EMPTY_PAGE_RATIO`
- Staging: `PDF_OCR_STAGING_BUCKET`, `PDF_OCR_STAGING_PREFIX`
- Polling: `TEXTRACT_POLL_INTERVAL_SECONDS`, `TEXTRACT_MAX_WAIT_SECONDS`

Secrets stay in env or a secret manager; do not commit AWS keys.
