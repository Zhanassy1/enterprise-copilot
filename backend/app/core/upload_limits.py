"""Upload size limits shared by API ingestion and storage backends."""

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# DOCX (OOXML) is a ZIP. These limits use central-directory metadata only (no full extraction).
# Mitigates pathological members / declared uncompressed sizes (zip-bomb class issues).
MAX_DOCX_ZIP_MEMBERS = 20_000
MAX_DOCX_UNCOMPRESSED_SINGLE = 128 * 1024 * 1024  # 128 MiB per entry
MAX_DOCX_UNCOMPRESSED_SUM = 512 * 1024 * 1024  # 512 MiB total declared


class UploadTooLargeError(Exception):
    """Raised when the incoming stream exceeds MAX_UPLOAD_BYTES during save_upload."""
