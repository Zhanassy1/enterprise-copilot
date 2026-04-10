"""Upload size limits shared by API ingestion and storage backends."""

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class UploadTooLargeError(Exception):
    """Raised when the incoming stream exceeds MAX_UPLOAD_BYTES during save_upload."""
