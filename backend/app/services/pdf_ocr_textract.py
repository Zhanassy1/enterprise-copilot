"""AWS Textract async document text detection (PDF in S3)."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextractOcrResult:
    text: str
    page_count: int
    job_id: str


def _textract_client():
    import boto3

    return boto3.client(
        "textract",
        region_name=settings.s3_region or None,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        endpoint_url=settings.s3_endpoint_url or None,
    )


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
    )


def parse_s3_storage_key(storage_key: str) -> tuple[str, str] | None:
    if not storage_key.startswith("s3://"):
        return None
    _, _, rest = storage_key.partition("s3://")
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        return None
    return bucket, key


def upload_local_pdf_to_staging(local_path: str) -> tuple[str, str]:
    """Upload file to staging bucket; caller must delete key after OCR."""
    bucket = (settings.pdf_ocr_staging_bucket or "").strip()
    if not bucket:
        raise ValueError("pdf_ocr_staging_bucket is not configured")
    prefix = (settings.pdf_ocr_staging_prefix or "ocr-staging").strip().strip("/")
    key = f"{prefix}/{uuid.uuid4()}.pdf"
    body = Path(local_path).read_bytes()
    client = _s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/pdf")
    return bucket, key


def delete_s3_object(bucket: str, key: str) -> None:
    try:
        _s3_client().delete_object(Bucket=bucket, Key=key)
    except Exception as e:
        logger.warning("failed to delete staging object s3://%s/%s: %s", bucket, key, e)


def _collect_all_blocks(client, job_id: str) -> list[dict]:
    blocks: list[dict] = []
    next_token: str | None = None
    while True:
        kwargs: dict = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.get_document_text_detection(**kwargs)
        blocks.extend(resp.get("Blocks") or [])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return blocks


def _blocks_to_page_text(blocks: list[dict]) -> tuple[str, int]:
    """LINE blocks grouped by Page, ordered by vertical position."""
    lines_by_page: dict[int, list[tuple[float, str]]] = {}
    max_page = 0
    for b in blocks:
        bt = b.get("BlockType")
        if bt == "PAGE":
            max_page = max(max_page, int(b.get("Page") or 0))
        if bt != "LINE":
            continue
        page = int(b.get("Page") or 1)
        max_page = max(max_page, page)
        text = (b.get("Text") or "").strip()
        if not text:
            continue
        geom = b.get("Geometry") or {}
        box = geom.get("BoundingBox") or {}
        top = float(box.get("Top", 0.0))
        lines_by_page.setdefault(page, []).append((top, text))

    if not lines_by_page and max_page == 0:
        return "", 0

    pages = sorted(lines_by_page.keys()) if lines_by_page else list(range(1, max_page + 1))
    if not pages and max_page:
        pages = list(range(1, max_page + 1))
    out_pages: list[str] = []
    upper = max(max_page, max(lines_by_page.keys()) if lines_by_page else 0)
    for pnum in range(1, upper + 1):
        lines = lines_by_page.get(pnum, [])
        lines.sort(key=lambda x: x[0])
        page_text = "\n".join(t for _, t in lines)
        out_pages.append(page_text)
    merged = "\n\f\n".join(out_pages).strip()
    return merged, upper if upper else len(out_pages)


def run_textract_document_text_detection(*, bucket: str, key: str) -> TextractOcrResult:
    client = _textract_client()
    start = client.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = start["JobId"]
    deadline = time.monotonic() + float(settings.textract_max_wait_seconds)
    poll = float(settings.textract_poll_interval_seconds)

    while time.monotonic() < deadline:
        resp = client.get_document_text_detection(JobId=job_id)
        status = resp.get("JobStatus")
        if status == "IN_PROGRESS":
            time.sleep(poll)
            continue
        if status == "FAILED":
            raise RuntimeError("Textract job failed")
        if status in ("SUCCEEDED", "PARTIAL_SUCCESS"):
            blocks = _collect_all_blocks(client, job_id)
            text, page_count = _blocks_to_page_text(blocks)
            return TextractOcrResult(text=text, page_count=page_count, job_id=job_id)
        time.sleep(poll)

    raise TimeoutError("Textract job timed out")
