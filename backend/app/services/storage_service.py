"""
Storage service — MinIO / Cloudflare R2 file operations.

This service abstracts all S3-compatible storage operations.
The same boto3 API works for both MinIO (local Docker) and Cloudflare R2 (production)
— only the endpoint URL and credentials change via environment variables.

Operations:
  - upload_file: store a file and return its storage key
  - get_presigned_url: generate a time-limited download URL
  - delete_file: remove a file from storage

Why presigned URLs?
  The client downloads files directly from MinIO/R2 without proxying through FastAPI.
  This reduces server load and bandwidth costs. The URL expires after 1 hour,
  limiting exposure if a URL is shared or leaked.

Why aiobotocore (async)?
  FastAPI's event loop is async. Using the synchronous boto3 in async endpoints
  would block the event loop, reducing throughput. aiobotocore provides the same
  boto3 interface but with async/await support.
"""

import uuid
from contextlib import asynccontextmanager

import aiobotocore.session
from botocore.exceptions import ClientError

from app.core.config import settings


@asynccontextmanager
async def _s3_client():
    """
    Async context manager that provides an S3-compatible client.

    Creates a fresh client per operation (simple and reliable for this scale).
    For very high throughput, a connection pool would be more efficient.
    """
    session = aiobotocore.session.get_session()
    async with session.create_client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
    ) as client:
        yield client


def _make_storage_key(ticket_id: uuid.UUID, filename: str) -> str:
    """
    Generate a unique, predictable storage key for a file.

    Format: tickets/<ticket_id>/<uuid>/<filename>
      - Grouped by ticket for easy bulk deletion.
      - UUID prefix prevents collisions if the same filename is uploaded twice.
    """
    unique_prefix = uuid.uuid4()
    return f"tickets/{ticket_id}/{unique_prefix}/{filename}"


async def upload_file(
    ticket_id: uuid.UUID,
    filename: str,
    content: bytes,
    mime_type: str,
) -> str:
    """
    Upload a file to S3-compatible storage and return the storage key.

    Args:
        ticket_id: UUID of the parent ticket (used for key organization).
        filename: Original filename (preserved in the key for readability).
        content: File bytes to upload.
        mime_type: MIME type set as ContentType metadata (for correct browser downloads).

    Returns:
        The storage key (used to retrieve or delete the file later).

    Raises:
        ClientError: If the upload fails (network error, permission denied, etc.)
    """
    key = _make_storage_key(ticket_id, filename)
    async with _s3_client() as s3:
        await s3.put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=key,
            Body=content,
            ContentType=mime_type,
        )
    return key


async def get_presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for direct client-side download.

    The URL is valid for `expires_in` seconds (default: 1 hour).
    After that, the client must request a fresh URL from the API.

    Args:
        storage_key: The object key in the bucket.
        expires_in: URL validity period in seconds.

    Returns:
        A pre-signed HTTPS URL the client can use to download the file.
    """
    async with _s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.STORAGE_BUCKET, "Key": storage_key},
            ExpiresIn=expires_in,
        )
    return url


async def delete_file(storage_key: str) -> None:
    """
    Delete a file from storage.

    Called when an attachment is removed via the DELETE endpoint.
    This always succeeds (no error if the key doesn't exist).
    """
    async with _s3_client() as s3:
        await s3.delete_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
