"""PDF ingestion pipeline vocabulary (classification, OCR)."""

PDF_KIND_TEXT_NATIVE = "text_native"
PDF_KIND_SCANNED = "scanned"
PDF_KIND_MIXED = "mixed"

PDF_KINDS = frozenset({PDF_KIND_TEXT_NATIVE, PDF_KIND_SCANNED, PDF_KIND_MIXED})
