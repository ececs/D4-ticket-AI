"""
Attachment routes — file upload, listing, download, and deletion.

Files are stored in MinIO (local dev) or Cloudflare R2 (production).
Both are S3-compatible, so the same boto3 code works for both environments.

Upload flow:
  1. Client sends a multipart/form-data POST with the file.
  2. Server validates size (≤10MB) and MIME type.
  3. Server uploads to MinIO/R2 with a unique storage key.
  4. Server saves attachment metadata to the DB.
  5. Server returns the attachment record with a presigned download URL.

Download flow:
  - Uses presigned URLs (time-limited) so the client downloads directly from
    MinIO/R2 without proxying the file through FastAPI. This reduces server load.

NOTE: Full implementation is in Día 3.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tickets", tags=["Attachments"])

# Full implementation added in Día 3
