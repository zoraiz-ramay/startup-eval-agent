"""S3 helpers for persistent PDF storage.

PDFs are stored in the S3 bucket defined by S3_BUCKET (env var).
When a PDF is needed but not present locally, _fetch_from_s3 downloads it
to a container-local cache dir so pypdf can read it without changes elsewhere.
"""
from __future__ import annotations

import os
import pathlib
import tempfile
import logging

log = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_BUCKET", "hydra-data-app-startup-evaluation-agent-hydra-pdfs")
S3_REGION = os.getenv("AWS_REGION", "us-west-2")
S3_PREFIX = "pdfs/"

# Container-local cache so we don't re-download the same PDF twice per session
_CACHE_DIR = pathlib.Path(tempfile.gettempdir()) / "pdf_s3_cache"


def _client():
    import boto3
    return boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("HYDRA_DATA_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("HYDRA_DATA_AWS_SECRET_ACCESS_KEY"),
    )


def _available() -> bool:
    return bool(
        os.environ.get("HYDRA_DATA_AWS_ACCESS_KEY_ID")
        and os.environ.get("HYDRA_DATA_AWS_SECRET_ACCESS_KEY")
    )


def fetch_pdf(basename: str) -> str:
    """Download a PDF from S3 to the local cache and return its local path.

    Returns empty string when unavailable (no creds, not found, or error).
    """
    if not _available():
        return ""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local = _CACHE_DIR / basename
    if local.exists():
        return str(local)
    key = f"{S3_PREFIX}{basename}"
    try:
        _client().download_file(S3_BUCKET, key, str(local))
        log.info("Downloaded s3://%s/%s -> %s", S3_BUCKET, key, local)
        return str(local)
    except Exception as exc:
        log.debug("S3 fetch failed for %s: %s", key, exc)
        return ""


def upload_pdf(local_path: str, basename: str | None = None) -> str:
    """Upload a local PDF file to S3. Returns the S3 key on success, '' on failure."""
    if not _available():
        return ""
    if basename is None:
        basename = pathlib.Path(local_path).name
    key = f"{S3_PREFIX}{basename}"
    try:
        _client().upload_file(local_path, S3_BUCKET, key)
        log.info("Uploaded %s -> s3://%s/%s", local_path, S3_BUCKET, key)
        return key
    except Exception as exc:
        log.error("S3 upload failed for %s: %s", local_path, exc)
        return ""


def list_pdfs() -> list[str]:
    """Return basenames of all PDFs stored in S3."""
    if not _available():
        return []
    try:
        paginator = _client().get_paginator("list_objects_v2")
        names = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                basename = key[len(S3_PREFIX):]
                if basename and basename.lower().endswith(".pdf"):
                    names.append(basename)
        return sorted(names)
    except Exception as exc:
        log.error("S3 list failed: %s", exc)
        return []


def delete_pdf(basename: str) -> bool:
    """Delete a PDF from S3. Returns True on success."""
    if not _available():
        return False
    key = f"{S3_PREFIX}{basename}"
    try:
        _client().delete_object(Bucket=S3_BUCKET, Key=key)
        cached = _CACHE_DIR / basename
        if cached.exists():
            cached.unlink()
        return True
    except Exception as exc:
        log.error("S3 delete failed for %s: %s", key, exc)
        return False


def presigned_url(basename: str, expiry: int = 3600) -> str:
    """Generate a pre-signed download URL for a PDF in S3."""
    if not _available():
        return ""
    key = f"{S3_PREFIX}{basename}"
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expiry,
        )
    except Exception as exc:
        log.error("S3 presign failed for %s: %s", key, exc)
        return ""
