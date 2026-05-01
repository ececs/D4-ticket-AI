"""
Attachment routes — file upload, listing, presigned download, and deletion.

Files are stored in MinIO (local dev) or Cloudflare R2 (production).
The same boto3-compatible code (via aiobotocore) works for both.

Upload validation:
  1. Size check: reject files exceeding MAX_ATTACHMENT_SIZE_MB (default 10MB).
     This check happens before writing to storage to avoid unnecessary uploads.
  2. MIME type check: only allow file types in the ALLOWED_MIME_TYPES list.
     We trust the Content-Type sent by the browser — for stricter security,
     python-magic could detect MIME from file bytes, but adds a C dependency.

Download:
  Returns a presigned URL valid for 1 hour. The client downloads directly from
  MinIO/R2 — FastAPI is not in the download path, keeping API server load low.

Deletion:
  Removes the file from MinIO/R2 first, then deletes the DB record.
  If storage deletion fails, we still remove the DB record to avoid orphan entries
  (the unreferenced file in storage is cheaper to clean up than a broken UI).
"""

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import CurrentUser, DB
from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.schemas.attachment import AttachmentOut
from app.services import storage_service

router = APIRouter(prefix="/tickets", tags=["Attachments"])

MAX_BYTES = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024


@router.get(
    "/{ticket_id}/attachments",
    response_model=list[AttachmentOut],
    summary="List attachments for a ticket",
)
async def list_attachments(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """
    Return all attachments for a ticket, with fresh presigned download URLs.

    Presigned URLs expire after 1 hour. The frontend should always fetch
    the attachment list fresh rather than caching the URLs long-term.
    """
    result = await db.execute(
        select(Attachment)
        .where(Attachment.ticket_id == ticket_id)
        .order_by(Attachment.created_at.asc())
    )
    attachments = result.scalars().all()

    # Generate presigned URLs for all attachments
    items = []
    for att in attachments:
        try:
            url = await storage_service.get_presigned_url(att.storage_key)
        except Exception:
            url = None  # Storage unavailable — still return the metadata
        items.append(AttachmentOut(
            id=att.id,
            ticket_id=att.ticket_id,
            uploader_id=att.uploader_id,
            filename=att.filename,
            size_bytes=att.size_bytes,
            mime_type=att.mime_type,
            created_at=att.created_at,
            download_url=url,
        ))
    return items


@router.post(
    "/{ticket_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment",
)
async def upload_attachment(
    ticket_id: uuid.UUID,
    file: UploadFile,
    db: DB,
    current_user: CurrentUser,
):
    """
    Upload a file to the ticket.

    Validations:
      - Ticket must exist.
      - File size must not exceed MAX_ATTACHMENT_SIZE_MB.
      - MIME type must be in ALLOWED_MIME_TYPES.

    The file is stored in MinIO/R2 and its metadata is saved to the DB.
    A presigned download URL is returned immediately.
    """
    # Verify the ticket exists
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not ticket_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Read file bytes — FastAPI buffers small files in memory, larger to temp disk
    content = await file.read()

    # Validate size
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_ATTACHMENT_SIZE_MB}MB limit",
        )

    # Validate MIME type
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{mime_type}' is not allowed",
        )

    filename = file.filename or f"attachment_{uuid.uuid4()}"

    # Upload to MinIO / Cloudflare R2
    try:
        storage_key = await storage_service.upload_file(
            ticket_id=ticket_id,
            filename=filename,
            content=content,
            mime_type=mime_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage upload failed: {str(e)}",
        )

    # Save metadata to DB
    attachment = Attachment(
        ticket_id=ticket_id,
        uploader_id=current_user.id,
        filename=filename,
        storage_key=storage_key,
        size_bytes=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    # Generate presigned URL for immediate download
    download_url = await storage_service.get_presigned_url(storage_key)

    return AttachmentOut(
        id=attachment.id,
        ticket_id=attachment.ticket_id,
        uploader_id=attachment.uploader_id,
        filename=attachment.filename,
        size_bytes=attachment.size_bytes,
        mime_type=attachment.mime_type,
        created_at=attachment.created_at,
        download_url=download_url,
    )


@router.delete(
    "/{ticket_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attachment",
)
async def delete_attachment(
    ticket_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: DB,
    current_user: CurrentUser,
):
    """
    Delete an attachment from storage and the database.

    Only the uploader can delete their own attachments.
    Storage deletion is attempted first; if it fails the DB record is still removed.
    """
    result = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.ticket_id == ticket_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Authorization: only the uploader can delete
    if attachment.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own attachments",
        )

    # Remove from storage (best-effort — don't fail the request if storage is down)
    try:
        await storage_service.delete_file(attachment.storage_key)
    except Exception:
        pass  # Log in production; for demo, we continue to clean up the DB record

    await db.delete(attachment)
    await db.commit()
