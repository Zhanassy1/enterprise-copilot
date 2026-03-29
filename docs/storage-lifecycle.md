# Storage and lifecycle

**Продуктовый контекст:** загрузки документов хранятся в local или S3; политика влияет на multi-replica API и retention. [deployment.md](deployment.md) — `PRODUCTION_REQUIRE_S3_BACKEND`.

## Backends

- **Local** (`STORAGE_BACKEND=local`): files under `upload_dir` (resolved under the backend root). Default for development.
- **S3** (`STORAGE_BACKEND=s3`): set `S3_BUCKET`, `S3_*` credentials, optional `S3_ENDPOINT_URL` for MinIO or other S3-compatible APIs. Presigned GET URLs are used when the client supports redirect.

Enable S3 when running multiple API replicas or when disks should not be the source of truth for uploads.

## Deduplication

- Per workspace, uploads with the same **SHA256** as an existing `ready` document reuse the existing row and delete the temporary upload bytes (no duplicate storage).

## Retention and soft delete

- `Document` rows use soft delete via `deleted_at`. Celery task `maintenance.purge_soft_deleted_documents` removes rows (and storage blobs) older than `DOCUMENT_RETENTION_DAYS_AFTER_SOFT_DELETE` (default 30). Schedule it with Celery beat or run manually in ops.

## Antivirus

- `scan_uploaded_file_safe` runs ClamAV when available; configuration is fail-open vs fail-closed in `antivirus.py`. Document policy in security review before production.

## Related

- [security.md](security.md) — secrets and S3 credentials  
- [runbook.md](runbook.md) — operations when ingestion fails  
- [deployment.md](deployment.md) — `PRODUCTION_REQUIRE_S3_BACKEND` and MinIO  
