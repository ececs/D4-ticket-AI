"""
Attachment routes.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, status
from app.core.config import settings
from app.core.dependencies import CurrentUser, DB
from app.schemas.attachment import AttachmentOut
from app.services import attachment_service

router = APIRouter(prefix="/tickets", tags=["Attachments"])

MAX_BYTES = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024


@router.get(
    "/{ticket_id}/attachments",
    response_model=List[AttachmentOut],
    summary="List attachments for a ticket",
)
async def list_attachments(ticket_id: uuid.UUID, db: DB, current_user: CurrentUser):
    """
    Return all attachments for a ticket, with fresh presigned download URLs.
    """
    return await attachment_service.list_attachments(db, ticket_id)


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
    """
    content = await file.read()

    # Size validation
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_ATTACHMENT_SIZE_MB}MB limit",
        )

    # MIME validation
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{mime_type}' is not allowed",
        )

    filename = file.filename or f"attachment_{uuid.uuid4()}"

    attachment = await attachment_service.create_attachment(
        db,
        ticket_id=ticket_id,
        uploader_id=current_user.id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    if not attachment:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    return attachment


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
    Delete an attachment. Only the original uploader can delete it.
    """
    success = await attachment_service.delete_attachment(
        db, attachment_id=attachment_id, actor_id=current_user.id
    )
    if not success:
        # Check if it's 404 or 403
        from sqlalchemy import select
        from app.models.attachment import Attachment
        exists = (await db.execute(select(Attachment).where(Attachment.id == attachment_id))).scalar_one_or_none()
        if not exists:
            raise HTTPException(status_code=404, detail="Attachment not found")
        raise HTTPException(status_code=403, detail="You can only delete your own attachments")
